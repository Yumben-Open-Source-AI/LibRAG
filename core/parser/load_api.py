import copy
import json
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List

from mineru.backend.pipeline.model_json_to_middle_json import result_to_middle_json as pipeline_result_to_middle_json
from mineru.backend.pipeline.pipeline_analyze import doc_analyze as pipeline_doc_analyze
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make as pipeline_union_make
from mineru.backend.vlm.vlm_analyze import doc_analyze as vlm_doc_analyze
from mineru.backend.vlm.vlm_middle_json_mkcontent import union_make as vlm_union_make
from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2, prepare_env, read_fn
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.utils.draw_bbox import draw_layout_bbox, draw_span_bbox
from mineru.utils.enum_class import MakeMode


def convert_file_type(input_path, output_dir, convert_type='pdf'):
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"The input file {input_path} does not exist.")

    if convert_type not in ['pdf', 'docx']:
        raise Exception(f"The input file type {convert_type} is not supported.")

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
        raise Exception(process.stderr.decode())


class DataLoader:
    def __init__(self, file_path):
        if isinstance(file_path, str):
            file_path = Path(file_path)
        self.file_path = file_path
        self.lang = os.getenv('MINERU_LANG')
        self.backend = os.getenv('MINERU_BACKEND')
        self.server_url = os.getenv('MINERU_SERVER_URL')
        self.page_count = self.load_file_page_number()

    def load_file_page_number(self) -> int:
        """
        解析文件页码
        Returns:
            page_number int:文档页码
        """
        import fitz
        pdf_content = fitz.open(self.file_path)
        return pdf_content.page_count

    def to_parse_file(self):
        try:
            # if self.backend == 'pipeline':
            #     return self.__use_pipeline_parse_file([], [])
            # else:
            if self.backend == 'vlm-sglang-client':
                return self.__use_vlm_parse_file()
        except Exception as e:
            print(e)

    @staticmethod
    def open_md(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.readlines()

    def __use_vlm_parse_file(
            self,
            f_draw_layout_bbox=True,
            f_dump_md=True,
            f_dump_middle_json=True,
            f_dump_model_output=True,
            f_dump_orig_pdf=True,
            f_dump_content_list=True,
            f_make_md_mode=MakeMode.MM_MD
    ):
        """
        使用VLM多模态模型逐页解析文件内容
        Arag:
            f_draw_layout_bbox: 是否绘制布局边界框
            f_dump_md: 是否输出markdown文件
            f_dump_middle_json: 是否要输出middle.json文件
            f_dump_model_output: 是否要输出model_output.txt文件
            f_dump_orig_pdf: 是否要输出源pdf文件
            f_dump_content_list: 是否要输出content_list.json文件
            f_make_md_mode: 制作 markdown 内容的模式，默认为 MM_MD
        Return:
            content_list: 按页读取的文件内容
        """
        return_content_list = []
        parse_method = "vlm"
        f_draw_span_bbox = False
        backend = self.backend[4:]
        pdf_all_bytes = read_fn(self.file_path)
        pdf_file_name = str(self.file_path.stem)
        temp_base_dir = tempfile.mkdtemp()

        for page_num in range(self.page_count):
            pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_all_bytes, page_num, page_num)
            output_dir = os.path.join(temp_base_dir, str(page_num))
            os.makedirs(output_dir, exist_ok=True)
            local_image_dir, local_md_dir = prepare_env(output_dir, pdf_file_name, parse_method)
            image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(local_md_dir)
            middle_json, infer_result = vlm_doc_analyze(pdf_bytes, image_writer=image_writer, backend=backend,
                                                        server_url=self.server_url)

            pdf_info = middle_json["pdf_info"]

            if f_draw_layout_bbox:
                draw_layout_bbox(pdf_info, pdf_bytes, local_md_dir, f"{pdf_file_name}_layout.pdf")

            if f_draw_span_bbox:
                draw_span_bbox(pdf_info, pdf_bytes, local_md_dir, f"{pdf_file_name}_span.pdf")

            if f_dump_orig_pdf:
                md_writer.write(
                    f"{pdf_file_name}_origin.pdf",
                    pdf_bytes,
                )

            if f_dump_md:
                image_dir = str(os.path.basename(local_image_dir))
                md_content_str = vlm_union_make(pdf_info, f_make_md_mode, image_dir)
                md_writer.write_string(
                    f"{pdf_file_name}.md",
                    md_content_str,
                )

            if f_dump_content_list:
                image_dir = str(os.path.basename(local_image_dir))
                content_list = vlm_union_make(pdf_info, MakeMode.CONTENT_LIST, image_dir)
                md_writer.write_string(
                    f"{pdf_file_name}_content_list.json",
                    json.dumps(content_list, ensure_ascii=False, indent=4),
                )

            if f_dump_middle_json:
                md_writer.write_string(
                    f"{pdf_file_name}_middle.json",
                    json.dumps(middle_json, ensure_ascii=False, indent=4),
                )

            if f_dump_model_output:
                model_output = ("\n" + "-" * 50 + "\n").join(infer_result)
                md_writer.write_string(
                    f"{pdf_file_name}_model_output.txt",
                    model_output,
                )

            cur_md_file = ' '.join(self.open_md(os.path.join(local_md_dir, f'{pdf_file_name}.md')))
            if cur_md_file != '':
                # 如果提取内容不为空则追加
                return_content_list.append(cur_md_file)
        shutil.rmtree(temp_base_dir, ignore_errors=True)

        print(return_content_list)

        return return_content_list

    def __use_pipeline_parse_file(
            self,
            pdf_file_names: list[str],
            p_lang_list: list[str],
            parse_method="ocr",
            p_formula_enable=True,
            p_table_enable=True,
            f_draw_layout_bbox=True,
            f_draw_span_bbox=True,
            f_dump_md=True,
            f_dump_middle_json=True,
            f_dump_model_output=True,
            f_dump_orig_pdf=True,
            f_dump_content_list=True,
            f_make_md_mode=MakeMode.MM_MD,
            start_page_id=0,
            end_page_id=None
    ):
        """
        使用ocr逐页解析文件内容
        Arag:
            pdf_file_names: 文件名
            p_lang_list: 文件语言类型，选择正确的语言可增强ocr准确性
            parse_method: 解析的方式，默认为ocr 可选auto、txt
            p_formula_enable: 是否开启公式解析
            p_table_enable: 是否开启表格解析
            f_draw_span_bbox: 是否绘制span边界框
            f_draw_layout_bbox: 是否绘制布局边界框
            f_dump_md: 是否输出markdown文件
            f_dump_middle_json: 是否要输出middle.json文件
            f_dump_model_output: 是否要输出model_output.txt文件
            f_dump_orig_pdf: 是否要输出源pdf文件
            f_dump_content_list: 是否要输出content_list.json文件
            f_make_md_mode: 制作 markdown 内容的模式，默认为 MM_MD
            start_page_id: 读取文件起始页面，默认下标从0开始
            end_page_id: 读取文件结尾页面，默认是None(即读取文件末尾)
        Return:
            content_list: 按页读取的文件内容
        """
        output_dir = ''
        pdf_bytes = read_fn(self.file_path)
        pdf_bytes_list = [pdf_bytes]
        for idx, pdf_bytes in enumerate(pdf_bytes_list):
            new_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, start_page_id, end_page_id)
            pdf_bytes_list[idx] = new_pdf_bytes

        infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = pipeline_doc_analyze(
            pdf_bytes_list, p_lang_list, parse_method=parse_method, formula_enable=p_formula_enable,
            table_enable=p_table_enable)

        for idx, model_list in enumerate(infer_results):
            model_json = copy.deepcopy(model_list)
            pdf_file_name = pdf_file_names[idx]
            local_image_dir, local_md_dir = prepare_env(output_dir, pdf_file_name, parse_method)
            image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(local_md_dir)

            images_list = all_image_lists[idx]
            pdf_doc = all_pdf_docs[idx]
            _lang = lang_list[idx]
            _ocr_enable = ocr_enabled_list[idx]
            middle_json = pipeline_result_to_middle_json(model_list, images_list, pdf_doc, image_writer, _lang,
                                                         _ocr_enable, p_formula_enable)

            pdf_info = middle_json["pdf_info"]

            pdf_bytes = pdf_bytes_list[idx]
            if f_draw_layout_bbox:
                draw_layout_bbox(pdf_info, pdf_bytes, local_md_dir, f"{pdf_file_name}_layout.pdf")

            if f_draw_span_bbox:
                draw_span_bbox(pdf_info, pdf_bytes, local_md_dir, f"{pdf_file_name}_span.pdf")

            if f_dump_orig_pdf:
                md_writer.write(
                    f"{pdf_file_name}_origin.pdf",
                    pdf_bytes,
                )

            if f_dump_md:
                image_dir = str(os.path.basename(local_image_dir))
                md_content_str = pipeline_union_make(pdf_info, f_make_md_mode, image_dir)
                md_writer.write_string(
                    f"{pdf_file_name}.md",
                    md_content_str,
                )

            if f_dump_content_list:
                image_dir = str(os.path.basename(local_image_dir))
                content_list = pipeline_union_make(pdf_info, MakeMode.CONTENT_LIST, image_dir)
                md_writer.write_string(
                    f"{pdf_file_name}_content_list.json",
                    json.dumps(content_list, ensure_ascii=False, indent=4),
                )

            if f_dump_middle_json:
                md_writer.write_string(
                    f"{pdf_file_name}_middle.json",
                    json.dumps(middle_json, ensure_ascii=False, indent=4),
                )

            if f_dump_model_output:
                md_writer.write_string(
                    f"{pdf_file_name}_model.json",
                    json.dumps(model_json, ensure_ascii=False, indent=4),
                )

    @property
    def supported_file_types(self) -> List[str]:
        """ 支持的文件类型 """
        return ['.pdf', '.png', '.jpeg', '.jpg']
