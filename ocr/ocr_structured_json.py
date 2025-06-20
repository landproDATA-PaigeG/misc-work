#####################
####### NOTES #######
#####################

# Files on the path: prepared-files/2/12/... [I think] are generated using the latest Document AI processor. 
# /prepared-files/2/12/001001/020100002/prepared contains Subdivisions. Subdivisions are n pages, depending on how many pages the original document has. Each PAGE has an accompanying .json and .txt file (i.e. 3 files per page).
# /prepared-files/2/12/001001/020200002/prepared contains ROS. ROS are 1 page, 1 PDF. Each PDF has an accompanying .json and .txt file (i.e. 3 files per document)
# TO MY KNOWLEDGE: Everything you will see IN PLATFORM currently, is sourced from landprodata-files/Subdivisions and were processed using the OLD vision model (not Document AI).

# Reference the accompanying screenshot for the modal David wants this service to run from. 

# STEP 1:
# For the Document in the .pdf file (visible) -> Send to new Document AI processer (OR pull it from the existing file paths (prepared_files/) noted above?? Not sure
# how he wants to reference this. Get the .json file(s). NOTE: Something is going on with the subdivisions files where they are producing a .json file for every page in the pdf. For this reason, see the recombine-files code below.
# 
# STEP 2:
# Recombine the files as necessary. 
# The following is the python code to fetch and recombine the prepared files. 

# Get the files -- AGAIN: MAY LOOK ENTIRELY DIFFERENT IN THE MODAL WORKFLOW
from collections import defaultdict
client = storage.Client()
bucket = client.get_bucket("prepared-files")
blobs = bucket.list_blobs(prefix="2/12/001001/020100002/prepared")
cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
#recent_blobs = [blob for blob in blobs if blob.time_created and blob.time_created > cutoff and not blob.name.endswith('.json')]
json_blobs = [blob for blob in blobs if blob.name.endswith('.json')]

def get_blob(bucket, blob_name):
    blob = bucket.blob(blob_name)
    return blob

blob_files = [json_blobs[name].name.split('prepared/')[1].split('_ocr')[0] for name in range(len(json_blobs))]

def group_paths_by_prefix(paths, prefix_length=6):
    groups = defaultdict(list)
    for path in paths:
        prefix = path[:prefix_length]
        groups[prefix].append(path)
    return dict(groups)

groups = group_paths_by_prefix(blob_files)

def fetch_file_group(file_prefix):
    '''Only applicable when you're fetching files from the prepared-files bucket. May be entirely irrelevant if you are pulling from the landprodata-files bucket, and/or have the object
    represented differently in the modal workflow.'''
    return ['2/12/001001/020100002/prepared/'+groups[file_prefix][fp]+'_ocr.json' for fp in range(len(groups[file_prefix]))] 

## Step 2.5: This function is important because it formats the text from the json file to preserve the 'paragraph' structure, which improves the accuracy of the OCR interpretation.
def make_text(file_group):
    file_text = """"""

    for file in file_group:
        get_text = get_blob(bucket, file).download_as_string()
        get_json = json.loads(get_text)
        text = get_json['text']
        
        file_text += f'\n# [FILE NAME: {file}]# \n' ## KEY FORMATTING CODE - THESE LINES DENOTE PAGE SEPARATION IN THE TEXT OUTPUT
        
        for page in get_json['pages']:
            for para in (page['paragraphs']): ## KEY FORMATTING CODE - USE PARAGRAPHS KEY, NOT 'BLOCKS'
                #segments:
                segments = para['layout']['textAnchor']['textSegments']
                try:
                    start = int(segments[0]['startIndex'])
                except:
                    start = 0
                
                end = int(segments[0]['endIndex'])
                

                file_text += f"\n# [PARAGRAPH] # \n {text[start:end]}" ## KEY FORMATTING CODE - THESE LINES DENOTE PARAGRAPH SEPARATION IN THE TEXT OUTPUT
    
    return file_text
## STEP 3: Make the API call (see below, commented out PHP code equivalent)
# Using pydantic to define the structure of the expected output from the OCR process.
class Person(BaseModel):
    first_name: Annotated[str, Field(description="A person's first name")]
    last_name: Annotated[str, Field(description="A person's last name")]
    title: Annotated[str, Field(description="A person's job title")]
    license_number: Annotated[str, Field(description="A person's license number, if applicable (likely for plats and surveys), where the person is a certified professional")]

class Entities(BaseModel):
    name: Annotated[str, Field(description="The entity's full name (including suffices like 'LLC', or 'inc')")]
    type: Annotated[Literal['state', 'county', 'city','company','parcel_name','other'], Field(description="Identify entities in the document and categorize by type. Use 'other' if the existing types don't fit the context")]
    inferred_context: Annotated[str, Field(description="A 200-character description of why this entity is present. Why are they referenced? What appears to be the purpose of their presence?")]

class TownshipSectionRange(BaseModel):
    range: Annotated[str, Field(description="Range")]
    section: Annotated[str, Field(description="Section")]
    township: Annotated[str, Field(description="Township")]

class Document(BaseModel):
    people: Annotated[Optional[List[Person]], Field("Returns a list of people identified from the extracted text")] 
    entities: Annotated[Optional[List[Entities]], Field("Returns a list of non-human entities identified from the extracted text")] 
    township_section_range: Annotated[TownshipSectionRange, Field(description="Township, section, and range. Return None if not present.")]
    legal_description: Annotated[str, Field(description="Legal description from the extracted text - it is critical this is extremely precise to the original text.")]
    #confidence_in_ocr: Annotated[float, Field(description="Based on the text, how confident are you that the OCR process was of acceptable quality? 0-100 scale only.")]
    #confidence_in_interpretation: Annotated[float, Field(description="Based on the text, how confident are you that you've interpreted the text appropriately? 0-100 scale only.")]

def ocr(oai_client, text):
    response = oai_client.responses.parse(
        model="gpt-4.1-mini", ## THIS MODEL IS CHEAPER AND SUFFICIENT FOR THE TASK.
        input=[
            {"role": "system", "content": "You are a helpful assistant at interpreting raw text extracted from complex land and parcel documents and surveys. You will always be provided one document at a time. \
             ##Precise instructions:\
             1. Carefully analyze the extracted text from the OCR process. Each input will delineate the files with the words '[FILE NAME]', which indicates page separation within the same document. \
                Similarly, the OCR processor identifies different paragraphs, which are delineated with [PARAGRAPH]. This should help make logical assumptions about the request. \
                Do not use prior knowledge or information from outside the context to answer the questions. Only use the information provided in the context to answer the questions.\
             2. Review the required JSON structure for the response\
             3. Fulfill the request to the best of your ability\
             4.  Review the input text structure to ensure the Legal Description is as complete and precise as possible. \
             Hints to help find the legal description: \
             - Use paragraph and header/subtitle hints, like isolating text between headers.\
             - Legal descriptions often explain a geographic polygon that is able to be closed when drawn.\
             - Note language that describes an area of ownerhip\
             - Note language like 'the point of beginning', and subsequent measurements. e.g. South 00°38 16 West, 305.80 feet\
             - Note when a block/paragraph of text seemingly terminates with an acreage statement.\
            ### A complete example of a legal description \
            # [PARAGRAPH] # \
            A portion of Lots 25, 26, and 27, Roberts and Hill Subdivision as is filed in Book 4 of Plats at Page 159, records of Ada County, Idaho located in the\
            Southeast 1/4 of the Northeast 1/4 of Section 14, T.4N., R.1E., B.M., City of Boise, Ada County, Idaho more particularly described as follows:\
            # [PARAGRAPH] # \
            Commencing at the East 1/4 corner of said Section 14, from which the Center 1/4 corner of said Section 14 bears North 88°50 47 West, 2635.27 feet;\
            thence on the East boundary line of said Section 14, North 00°38 16 East, 1185.68 feet; thence leaving said East boundary line, North 88°35 49 West, 25.00\
            feet to the westerly right-of-way line of N. Bogart Lane and the REAL POINT OF BEGINNING;\
            # [PARAGRAPH] # \
            thence on said westerly right-of-way line the following seven (7) courses and distances:\
            # [PARAGRAPH] # \
            South 00°38 16  West, 305.80 feet;\
            South 07°14 08  West, 65.87 feet;\
            # [PARAGRAPH] # \
            South 03°53 20  West, 48.39 feet;\
            # [PARAGRAPH] # \
            71.67 feet along the arc of curve to the right having a radius of 60.00 feet, a central angle of 68°26 22  and a long chord which bears South\
            38°06 30  West, 67.48 feet;\
            # [PARAGRAPH] # \
            52.27 feet along the arc of curve to the right having a radius of 135.00 feet, a central angle of 22°11 07  and a long chord which bears South\
            83°25 15  West, 51.95 feet;\
            # [PARAGRAPH] # \
            81.83 feet along the arc of a curve to the left having a radius of 615.00 feet, a central angle of 07°37 26  and a long chord which bears North\
            89°17 54  West, 81.77 feet;\
            # [PARAGRAPH] #  \
            16.80 feet along the arc of a curve to the right having a radius of 585.00 feet, a central angle of 01°38 44  and a long chord which bears South\
            87°42 44  West, 16.80 feet to the northerly right-of-way line of W. Hill Road Parkway;\
            # [PARAGRAPH] # \
            thence on said northerly right-of-way line the following two (2) courses and distances:\
            # [PARAGRAPH] # \
            103.13 feet along the arc of a curve to the left having a radius of 1,193.92 feet, a central angle of 04°56 57  and a long chord which bears North\
            86°30 32  West, 103.10 feet;\
            # [PARAGRAPH] # \
            North 88°59 01  West, 659.42 feet to the west boundary line of said Lot 27, Roberts and Hill Subdivision;\
            # [PARAGRAPH] # \
            thence on said west boundary line, North 00°35 32  East, 608.79 feet to the north boundary line of said Roberts and Hill Subdivision;\
            thence on said north boundary line, South 88°35 49  East, 814.40 feet;\
            # [PARAGRAPH] # \
            thence leaving said north boundary line, South 00°38 16  West, 125.00 feet;\
            thence South 88°35 49  East, 150.00 feet to the REAL POINT OF BEGINNING.\
            # [PARAGRAPH] # \
            Containing 12.93 acres, more or less.\
            ## Formatting Instructions\
             Use as precise of language as possible. Do not include any explanation in the reply. Only include the extracted information in the reply.\
             Only in 'inferred_context' are you allowed to practice freedom of explanation."},
            {"role": "user", "content": f"Return your interpretation of the following OCR text using the structured output model provided: {text}"}
        ],
        text_format = Document
    )
    return response

## PHP VERSION OF THE ABOVE CODE


# <?php

# class Person {
#     /** @var string A person's first name */
#     public string $first_name;

#     /** @var string A person's last name */
#     public string $last_name;

#     /** @var string A person's job title */
#     public string $title;

#     /** @var string A person's license number, if applicable */
#     public string $license_number;
# }

# class Entity {
#     /** @var string The entity's full name (including 'LLC', 'Inc', etc) */
#     public string $name;

#     /**
#      * @var string One of: 'state', 'county', 'city', 'company', 'parcel_name', 'other'
#      */
#     public string $type;

#     /** @var string Description of why this entity is referenced in the document */
#     public string $inferred_context;
# }

# class TownshipSectionRange {
#     /** @var string */
#     public string $range;

#     /** @var string */
#     public string $section;

#     /** @var string */
#     public string $township;
# }

# class Document {
#     /** @var Person[]|null */
#     public ?array $people = null;

#     /** @var Entity[]|null */
#     public ?array $entities = null;

#     /** @var TownshipSectionRange|null */
#     public ?TownshipSectionRange $township_section_range = null;

#     /** @var string Precise legal description from OCR text */
#     public string $legal_description;
# }


## STEP 4: store the full response in a database log file

## STEP 5: Store the response.output_parsed.model_dump() in the OCR Matches column as a json object that we can later parse