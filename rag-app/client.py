"""
Knowledge‑Base Manager & Recall‑Test Demo
Gradio 5.25.2  +  gradio_modal ≥0.2
"""

import os, random, functools, inspect, logging, pprint
import shutil

import gradio as gr
import pandas as pd
from gradio_modal import Modal

import sys

sys.path.append(os.path.abspath(os.path.join('./tools')))
from http_utils import RequestHandler

ALL_STRATEGY = {
    '按页切割': 'page_split',
    '按目录切割': 'catalog_split',
    '智能上下文切割': 'automate_judgment_split'
}

MAX_ROWS = 20

request = RequestHandler('http://127.0.0.1:13113/ai/')


def log_io(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        arg_names = inspect.getfullargspec(func).args
        bound = dict(zip(arg_names, args)) | kwargs
        logging.info(f"[CALL] {func.__name__} → {pprint.pformat(bound, compact=True)}")
        result = func(*args, **kwargs)
        logging.info(f"[RETURN] {func.__name__} ← {pprint.pformat(result, compact=True)}")
        return result

    return wrapper


def get_kb_choices():
    all_kbs = request.safe_send_request('knowledge_bases', 'GET')

    return gr.update(choices=[f"{str(kb['kb_id'])}:{kb['kb_name']}" for kb in all_kbs])


def get_kb_table(include_key=None):
    all_kbs = request.safe_send_request('knowledge_bases', 'GET')

    return pd.DataFrame(
        [{'知识库id': kb['kb_id'], '知识库名称': kb['kb_name'], '知识库描述': kb['kb_description']} for kb in all_kbs]
    )


def file_table_from_kb(kb_id):
    kb_db = request.safe_send_request(f'knowledge_base/{kb_id}', method='GET')
    show_document_info = []
    for document in kb_db['documents']:
        show_document_info.append({
            'document_id': document['document_id'],
            '文档名称': document['document_name'],
            '文档描述': document['document_description'],
        })

    return pd.DataFrame(show_document_info) if kb_db else pd.DataFrame()


def make_preview_cb():
    """ 动态控制行显隐 & 预览表格 """

    @log_io
    def preview_upload(paths):
        # 生成DataFrame
        data_frame = pd.DataFrame([
            {
                "文件名": os.path.basename(p),
                "大小(KB)": round(os.path.getsize(p) / 1024, 2),
                "文件类型": os.path.splitext(p)[1][1:]
            }
            for p in (paths or [])
        ])
        # 更新行组件
        updates = []
        for i in range(MAX_ROWS):
            if paths and i < len(paths):
                updates += [
                    gr.Row.update(visible=True),
                    gr.update(value=os.path.basename(paths[i]),
                              visible=True, interactive=False),
                    gr.update(visible=True, interactive=True,
                              value="智能上下文切割"),
                ]
            else:
                updates += [
                    gr.Row.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                ]
        return data_frame, *updates

    return preview_upload


def __upload_file(kb_id, files, strategies):
    """ 上传文件 """
    base_dir = './files/'
    files_info = []
    for file, strategy in zip(files, strategies):
        file_name = os.path.basename(file)
        file_path = os.path.abspath(os.path.join(base_dir, file_name))
        with open(file, 'rb') as source:
            with open(file_path, 'wb') as target:
                shutil.copyfileobj(source, target)
        files_info.append({
            'kb_id': kb_id,
            'file_path': file_path,
            'policy_type': ALL_STRATEGY[strategy]
        })

    request.safe_send_request('upload', 'POST', json={
        'items': files_info
    })


def submit_append_file(kb_id, files, *strategies):
    """ 追加提交每个文件解析及切割策略 """
    __upload_file(kb_id, files, strategies)

    gr.Info(f"成功追加{len(files)} 个文件")
    return (
        Modal(visible=False),
        file_table_from_kb(kb_id)
    )


def submit_create_kb(name, desc, files, *strategies):
    """ 新增知识库 & 提交每个文件解析及切割策略 """
    if not name.strip():
        gr.Warning("知识库名称不能为空")
        return Modal(visible=True)
    if not desc.strip():
        gr.Warning("知识库描述不能为空")
        return Modal(visible=True)
    if not files:
        gr.Warning("请选择至少一个文件")
        return Modal(visible=True)

    # 新增知识库数据
    new_kb = request.safe_send_request('knowledge_bases', 'POST', json={
        'kb_name': name,
        'kb_description': desc,
        'keywords': ''
    })
    kb_id = new_kb['kb_id']

    base_dir = './files/'
    os.makedirs(base_dir, exist_ok=True)

    __upload_file(kb_id, files, strategies)

    gr.Info(f"知识库『{name}』已创建，共 {len(files)} 个文件")
    return (
        Modal(visible=False),
        get_kb_table()
    )


def enter_kb(evt: gr.SelectData):
    selected_id = evt.row_value[0]
    selected_name = evt.row_value[1]
    if selected_id is None:
        return None, gr.update(visible=False), pd.DataFrame()

    return (
        selected_id,
        gr.update(
            value=file_table_from_kb(selected_id),
            label=f"{selected_name} - 文件列表"
        ),
        gr.update(interactive=True),
    )


def add_files_to_kb(paths, idx, state):
    kb = state[idx]
    for p in paths:
        kb["files"].append({"name": os.path.basename(p), "size": round(os.path.getsize(p) / 1024, 2)})
    gr.Info(f"已向『{kb['name']}』追加 {len(paths)} 个文件")
    return file_table_from_kb(kb)


def recall_clear():
    return None, None, pd.DataFrame()


def recall_test(query: str, kb_info: str):
    if not query.strip():
        gr.Warning("请输入查询内容")
        return pd.DataFrame()
    if not kb_info:
        gr.Warning("请选择知识库")
        return pd.DataFrame()

    kb_id, kb_name = kb_info.split(':')
    paragraphs = request.safe_send_request('recall', 'GET', body={
        'kb_id': kb_id,
        'question': query
    })

    paragraphs = [{'paragraph_id': par['paragraph_id'], '段落摘要': par['summary'], '段落内容': par['content'],
                   '来源描述': par['parent_description'], '分数': par['score']} for par in paragraphs]

    return pd.DataFrame(paragraphs)


css = """
    /* 限制表格的宽度并允许换行 */
    table td {
        white-space: pre-line;
    }
    
    /* 设置markdown文字居中 */
    div[data-testid="markdown"] {
        text-align: center;
        font-size: 30px;
    }
"""

# ---------- UI ----------
with gr.Blocks(title="LibRAG", css=css) as demo:
    kb_selected_idx = gr.State(None)

    gr.Markdown('# LibRAG')

    with gr.Tabs(selected=0):
        # 知识库管理tab
        with gr.TabItem("知识库管理"):
            with gr.Row():
                with gr.Column(scale=7):
                    kb_df = gr.Dataframe(
                        value=get_kb_table,
                        interactive=False,
                        max_height=260
                    )

                with gr.Column(scale=2):
                    create_btn = gr.Button("创建知识库", variant="primary")
                    appends_files_btn = gr.Button('追加新文件', variant='primary', interactive=False)

            with gr.Column(visible=True) as kb_detail_col:
                kb_files_df = gr.Dataframe(headers=['document_id', '文档名称', '文档描述'], interactive=True,
                                           max_height=650)

            create_modal = Modal(visible=False)
            with create_modal:
                gr.Markdown("## 创建新知识库")
                with gr.Row():
                    name_tb = gr.Textbox(label="知识库名称")
                    desc_tb = gr.Textbox(label="知识库描述")

                with gr.Row():
                    with gr.Column(scale=4):
                        files_up = gr.File(file_count="multiple", label="上传文件（多选）", type="filepath")

                    with gr.Column(scale=4):
                        row_comps, dd_inputs = [], []
                        for i in range(MAX_ROWS):
                            with gr.Row(visible=False) as r:
                                tb = gr.Textbox(label=f"文件{i + 1}")
                                dropdown = gr.Dropdown(list(ALL_STRATEGY.keys()), label="切割策略")
                            row_comps.extend([r, tb, dropdown])
                            dd_inputs.append(dropdown)

                # 已上传文件预览
                preview_df = gr.Dataframe(interactive=False, max_height=150)
                with gr.Row():
                    submit_btn = gr.Button("创建知识库并提交文件", variant="primary")
                    cancel_btn = gr.Button("取消")

            appends_modal = Modal(visible=False)
            with appends_modal:
                gr.Markdown("## 知识库追加新文件解析")
                with gr.Row():
                    with gr.Column(scale=4):
                        add_files_up = gr.File(file_count="multiple", label="上传文件（多选）", type="filepath")

                    with gr.Column(scale=5):
                        add_row_comps, add_inputs = [], []
                        for i in range(MAX_ROWS):
                            with gr.Row(visible=False) as r:
                                tb = gr.Textbox(label=f"文件{i + 1}")
                                dropdown = gr.Dropdown(list(ALL_STRATEGY.keys()), label="切割策略")
                            add_row_comps.extend([r, tb, dropdown])
                            add_inputs.append(dropdown)

                append_preview_df = gr.Dataframe(interactive=False, max_height=150)
                with gr.Row():
                    append_submit_btn = gr.Button("追加文件", variant="primary")
                    cancel_files_btn = gr.Button("取消")

        # 召回测试tag
        with gr.TabItem("召回测试"):
            with gr.Row():
                query_tb = gr.Textbox(label="输入内容", placeholder="请输入查询，建议采用陈述性语句", lines=1, scale=6)
                recall_dd = gr.Dropdown(label="选择知识库", scale=2)
                with gr.Column(scale=2):
                    recall_btn = gr.Button("测试召回", variant="primary")
                    clear_btn = gr.Button("重置查询", variant="secondary")
            recall_df = gr.Dataframe(headers=["paragraph_id", "段落摘要", "段落内容", "来源描述", "分数"],
                                     interactive=False, max_height=650, elem_id='recall-df')

    # 事件绑定
    create_btn.click(lambda: Modal(visible=True), None, create_modal)
    cancel_btn.click(lambda: Modal(visible=False), None, create_modal)
    appends_files_btn.click(lambda: Modal(visible=True), None, appends_modal)
    cancel_files_btn.click(lambda: Modal(visible=False), None, appends_modal)

    files_up.change(
        make_preview_cb(),
        inputs=[files_up],
        outputs=[preview_df, *row_comps]  # 控制显隐
    )

    submit_btn.click(
        submit_create_kb,
        inputs=[name_tb, desc_tb, files_up, *dd_inputs],
        outputs=[create_modal, kb_df],
    )

    kb_df.select(
        enter_kb,
        outputs=[kb_selected_idx, kb_files_df, appends_files_btn],
    )

    add_files_up.change(
        make_preview_cb(),
        inputs=[add_files_up],
        outputs=[append_preview_df, *add_row_comps],
    )

    append_submit_btn.click(
        submit_append_file,
        inputs=[kb_selected_idx, add_files_up, *add_inputs],
        outputs=[appends_modal, kb_files_df]
    )

    recall_btn.click(
        recall_test,
        inputs=[query_tb, recall_dd],
        outputs=recall_df
    )

    clear_btn.click(
        recall_clear,
        outputs=[query_tb, recall_dd, recall_df]
    )

    demo.load(
        get_kb_choices,
        outputs=[recall_dd]
    )

# ---------- 启动 ----------
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        # auth=('yumben', '123456')
    )
