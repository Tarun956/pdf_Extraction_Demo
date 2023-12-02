import tabula
from fastapi import FastAPI, UploadFile, File
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfReader
import re
from langdetect import detect
from pdf2image import convert_from_path
from io import BytesIO
import fitz
import os
import uvicorn
import json
from fastapi.middleware.cors import CORSMiddleware
from summa import summarizer
import spacy
from spacy.lang.en.stop_words import STOP_WORDS
from string import punctuation
from heapq import nlargest
import random
import PyPDF2

app = FastAPI()
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

@app.get("/get_stat/")
def get_stats_of_files(name: str):
    current_directory = os.getcwd()
    result =  get_stats_of_file(curr_file_path= f"{current_directory}\\{name}")
    print(result)
    return json.dumps(result)

def get_stats_of_file(curr_file_path):
    pdf_document = fitz.open(curr_file_path)

    total_words = 0
    headings = 0
    sub_headings = 0
    text_sizes = []
    langs = []
    image_count = 0

    total_pdf_text = []


    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        page_text = page.get_text()

        try:
            langs.append(detect(page_text.strip()[:100]))
        except:
            pass

        hdgs = re.findall(r'\b([A-Z\d]+:)', page_text, re.I)
        hdgs_result = [h.strip() for h in hdgs]
        headings += len(hdgs_result)

        sub_hdgs = re.findall(r'([a-z]+:)', page_text, re.I)
        sub_headings += len(sub_hdgs)

        # Extract font sizes from the page
        for block in page_text.split('\n'):
            for span in block.split(' '):
                if span.strip().isdigit():
                    text_sizes.append(int(span.strip()))

        # Count images in the page
        image_list = page.get_images(full=True)
        image_count += len(image_list)

        # Count total words
        total_words += len(page_text.split())
        total_pdf_text.append(page_text.strip())

    pdf_document.close()

    ### picking text size dominating one
    final_text_sizes = []
    for sz in text_sizes:
        if sz in [10,11,12,13,14,15,16,17,18,19,20]:
            final_text_sizes.append(sz)

    text_sizes_count = {}
    for elem in final_text_sizes:
        if elem not in text_sizes_count:
            text_sizes_count[elem] = 1
        else:
            already_count = text_sizes_count[elem]
            text_sizes_count[elem] = already_count+1

    Keymax = None
    if text_sizes_count:
        Keymax = max(zip(text_sizes_count.values(), text_sizes_count.keys()))[1]

    final_total_pdf_text = ' '.join(total_pdf_text)
    result = {}
    result["total_words"] = str(total_words) if total_words != 0 else 'NA'
    result["languages"] = str(set(langs))
    result["Is_english_present"] = "en" in langs
    result["total_headings"] = str(headings) if total_words != 0 else 'NA'
    result["total_subheadings"] = str(sub_headings) if total_words != 0 else 'NA'
    result["text_sizes"] = Keymax if Keymax else 'NA'
    result["total_images_count"] = str(image_count)
    result["Font_color_majority"] = "Black" if total_words != 0 else 'NA'
    result["total_pdf_text"] = final_total_pdf_text
    
    # table_count = get_table_count(curr_file_path)
    table_count = count_tables_in_pdf(curr_file_path)
    result["total_tables"] = str(table_count)

    pdf_metadata = get_pdf_metadata(curr_file_path)

    available_links = []

    try:
        print("Extracted Links:")
        extracted_links = extract_links(final_total_pdf_text)
        for link in extracted_links:
            available_links.append(link)
    except:
        pass


    result['links'] = available_links

    result["pdf_metadata"] = pdf_metadata
  
    summary = generate_summary(final_total_pdf_text)
    
    result['summary'] = summary
    
    return result

def get_table_count(pdf_path):
    """Counts the number of tables in a PDF file.

    Args:
        pdf_path: The path to the PDF file.

    Returns:
        The number of tables in the PDF file.
    """
    try:
        # Read the PDF file and extract all of the tables using tabula
        print("india")
        tables = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
        print("tablesffffffffffff")
        return len(tables)
    except Exception as e:
        print(e)

        return 0
# def count_tables_in_pdf(pdf_path):
#     tables_count = 0

#     with open(pdf_path, 'rb') as pdf_file:
#         pdf_reader = PyPDF2.PdfReader(pdf_file)

#         for page_num in range(len(pdf_reader.pages)):
#             page = pdf_reader.getPage(page_num)
#             page_text = page.extractText()

#             # Use regex to identify potential table-like structures
#             # Modify the regex pattern based on the structure of tables in your PDF
#             table_patterns = [
#                 r'\b[A-Z][^\.\n]*[A-Z][^\.\n]*\b\s+[\d\.,\(\)-]+(?:\s+[\d\.,\(\)-]+)*\n',
#                 # Add more patterns if tables have different structures
#             ]

#             for pattern in table_patterns:
#                 matches = re.findall(pattern, page_text)
#                 tables_count += len(matches)

#     return tables_count

def count_tables_in_pdf(pdf_path):
    tables_count = 0

    with open(pdf_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)

        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()

            # Use regex to identify potential table-like structures
            # Modify the regex pattern based on the structure of tables in your PDF
            table_patterns = [
                r'\b[A-Z][^\.\n]*[A-Z][^\.\n]*\b\s+[\d\.,\(\)-]+(?:\s+[\d\.,\(\)-]+)*\n',
                # Add more patterns if tables have different structures
            ]

            for pattern in table_patterns:
                matches = re.findall(pattern, page_text)
                tables_count += len(matches)

    return tables_count

def get_pdf_metadata(pdf_path):
    metadata = {}
    try:
        with fitz.open(pdf_path) as pdf_document:
            print(pdf_document.metadata)
            metadata['Title'] = pdf_document.metadata.get('title', 'N/A')
            metadata['Author'] = pdf_document.metadata.get('author', 'N/A')
            # metadata['Subject'] = pdf_document.metadata.get('subject', 'N/A')
            metadata['Creator'] = pdf_document.metadata.get('creator', 'N/A')
            metadata['Producer'] = pdf_document.metadata.get('producer', 'N/A')
            metadata['Creation_Date'] = pdf_document.metadata.get('creationDate', 'N/A')
            metadata['Modification_Date'] = pdf_document.metadata.get('modDate', 'N/A')
            metadata['Number_of_Pages'] = pdf_document.page_count
    except Exception as e:
        print(f"Error: {e}")

    return metadata\

def extract_images_from_pdf(pdf_path, image_folder):
    pdf_document = fitz.open(pdf_path)

    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]
        image_list = page.get_images(full=True)

        for img_index, img in enumerate(image_list):
            image_index, base_image = img
            image_bytes = base_image["image"]

            image_filename = f"{image_folder}/page{page_num + 1}_img{img_index + 1}.png"

            with open(image_filename, "wb") as image_file:
                image_file.write(image_bytes)

    pdf_document.close()

def extract_links(text):
    
    url_pattern = re.compile(r'https?://\S+|www\.\S+')

    links = re.findall(url_pattern, text)

    return links

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with fitz.open(pdf_path) as pdf_document:
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                text += page.get_text()
    except Exception as e:
        print(f"Error: {e}")
    return text

def generate_summary(text, ratio=0.2):
    try:
        summary = summarizer.summarize(text, ratio=ratio)
        return summary
    except:
        sums = text.split('.')
        try:
            sum_values = []
            if len(sums) >= 4:
                for _ in range(len(sums)):
                    value = random.randint(1, len(sums))
                    if len(sum_values)<=4 and value not in sum_values:
                        sum_values.append(value)

            sum_values.sort()
            for val in sum_values:
                final_summary += sums[val]
            return final_summary
        except:
            pass


if __name__ == "__main__":
    
    uvicorn.run(app, host="0.0.0.0", port=5000)

# def summarize(text, per):
#     nlp = spacy.load('en_core_web_sm')
#     doc= nlp(text)
#     tokens=[token.text for token in doc]
#     word_frequencies={}
#     for word in doc:
#         if word.text.lower() not in list(STOP_WORDS):
#             if word.text.lower() not in punctuation:
#                 if word.text not in word_frequencies.keys():
#                     word_frequencies[word.text] = 1
#                 else:
#                     word_frequencies[word.text] += 1
#     max_frequency=max(word_frequencies.values())
#     for word in word_frequencies.keys():
#         word_frequencies[word]=word_frequencies[word]/max_frequency
#     sentence_tokens= [sent for sent in doc.sents]
#     sentence_scores = {}
#     for sent in sentence_tokens:
#         for word in sent:
#             if word.text.lower() in word_frequencies.keys():
#                 if sent not in sentence_scores.keys():                            
#                     sentence_scores[sent]=word_frequencies[word.text.lower()]
#                 else:
#                     sentence_scores[sent]+=word_frequencies[word.text.lower()]
#     select_length=int(len(sentence_tokens)*per)
#     summary=nlargest(select_length, sentence_scores,key=sentence_scores.get)
#     final_summary=[word.text for word in summary]
#     summary=''.join(final_summary)
#     return summary


# Get the path to the PDF file
# pdf_path = "/content/ACFrOgCnVFkjnidLiOabke2j-sdMa5NsWPD_kUASChfblcqOzP94T-04ABxGAxHi7WFqeAnCEj3IYwh3ffEnUPxa_bKhwCgrvp5ANj1sp_O8dEruLh7cbRFgx7IFEa12nKcgDGEWHkLkCYGq7ZbSsMNCgkdYreYNzRe-kS2A2g==.pdf"

# Call the modified function to get the stats
# result = get_stats_of_file(pdf_path)

# Print the results
# print(result)


