import os
import subprocess
from typing import List

from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.utils.office_to_pdf import ConvertToPdfError


def read_md_file(name_without_suffix):
    with open(f'{name_without_suffix}.md', 'r', encoding='utf-8') as file:
        data = file.read()
    return data


def convert_file_type(input_path, output_dir, convert_type='pdf'):
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"The input file {input_path} does not exist.")

    if convert_type not in ['pdf', 'docx']:
        raise SupportedPdfParseMethod

    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        'soffice',
        '--headless',
        '--convert-to', convert_type,
        '--outdir', str(output_dir),
        str(input_path)
    ]

    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if process.returncode != 0:
        raise ConvertToPdfError(process.stderr.decode())


def convert_pdf_to_md(file_path):
    """
    文档解析PDF转化为机器可读格式的工具 pdf to markdown
    """

    # args
    pdf_file_name = os.path.abspath(file_path)
    name_without_suffix = ''.join(pdf_file_name.split(".")[:-1])

    # prepare env
    local_image_dir, local_md_dir = "output/images", "output"
    image_dir = str(os.path.basename(local_image_dir))

    os.makedirs(local_image_dir, exist_ok=True)

    image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(
        local_md_dir
    )

    # read bytes
    reader1 = FileBasedDataReader("")
    pdf_bytes = reader1.read(pdf_file_name)  # read the pdf content

    # proc
    ## Create Dataset Instance
    ds = PymuDocDataset(pdf_bytes)

    ## inference
    if ds.classify() == SupportedPdfParseMethod.OCR:
        ds.apply(doc_analyze, ocr=True).pipe_ocr_mode(image_writer).dump_md(
            md_writer, f"{name_without_suffix}.md", image_dir
        )
    else:
        ds.apply(doc_analyze, ocr=False).pipe_txt_mode(image_writer).dump_md(
            md_writer, f"{name_without_suffix}.md", image_dir
        )
    return read_md_file(name_without_suffix)


class PDFLoader:
    def __init__(self, file_path):
        self.file_path = file_path

    def load_file(self) -> List:
        import fitz
        pdf_content = fitz.open(self.file_path)
        page_contents = [page.get_text() for page in pdf_content.pages()]
        return page_contents
