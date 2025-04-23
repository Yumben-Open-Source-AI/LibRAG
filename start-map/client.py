"""
Knowledge‑Base Manager & Recall‑Test Demo
Gradio 5.25.2  +  gradio_modal ≥0.2
"""

import os, random, functools, inspect, logging, pprint
import gradio as gr
import pandas as pd
from gradio_modal import Modal

from tools.http_utils import RequestHandler

file_split_state = []

ALL_STRATEGY = {
    '按页切割': 'page_split',
    '按目录切割': 'catalog_split',
    '智能上下文切割': 'automate_judgment_split'
}

MAX_ROWS = 20

request = RequestHandler('http://127.0.0.1:13113/ai/')


# # ============ 日志装饰器（打印所有输入 / 输出） ============
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s | %(levelname)s | %(message)s"
# )


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


# ==========================================================

# ---------- 初始虚拟数据 ----------
kb_state_init = [
    {
        "name": "DemoKB",
        "files": [
            {"name": "demo_说明.pdf", "size": 123.4},
            {"name": "requirements.txt", "size": 2.7},
        ],
    }
]


def get_kb_table(include_key=None):
    all_kbs = request.safe_send_request('knowledge_bases', 'GET')

    return pd.DataFrame(
        [{"已有知识库名称": kb['kb_name'], "已有知识库描述": kb['kb_description']} for kb in all_kbs]
    )


def file_table_from_kb(kb):
    return pd.DataFrame(kb["files"]) if kb else pd.DataFrame()


def make_preview_cb():
    """闭包：动态控制行显隐 + 预览表格"""

    @log_io
    def preview_upload(paths):
        # 1) 生成右下 DataFrame 预览
        df = pd.DataFrame([
            {"文件名": os.path.basename(p),
             "大小(KB)": round(os.path.getsize(p) / 1024, 2),
             "文件类型": os.path.splitext(p)[1][1:]}
            for p in (paths or [])
        ])
        # 2) 更新行组件
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
        return df, *updates

    return preview_upload


def submit_create_kb(name, desc, files, *strategies):
    """保存知识库 + 每个文件的切割策略"""
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
    print(new_kb)

    for file, strategy in zip(files, strategies):
        with open(file, 'rb') as f:
            request.safe_send_request('upload', 'POST', body={
                'kb_id': new_kb['kb_id'],
                'policy_type': strategy
            }, files={'file': f})

    gr.Info(f"知识库『{name}』已创建，共 {len(files)} 个文件")
    return (
        Modal(visible=False),  # 关闭弹窗
        get_kb_table()  # 刷新左侧总表
    )


def enter_kb(evt: gr.SelectData, state):
    if evt.index is None:
        return None, gr.update(visible=False), pd.DataFrame()

    if isinstance(evt.index, list):
        first = evt.index[0]
        row_idx = first[0] if isinstance(first, tuple) else first
    elif isinstance(evt.index, tuple):
        row_idx = evt.index[0]
    else:
        row_idx = evt.index

    if row_idx is None or row_idx >= len(state):
        return None, gr.update(visible=False), pd.DataFrame()

    return (
        row_idx,
        gr.update(visible=True),
        gr.update(
            value=file_table_from_kb(state[row_idx]),
            label=f"文件列表 - {state[row_idx]['name']}"
        )
    )


def add_files_to_kb(paths, idx, state):
    if idx is None or idx >= len(state) or not paths:
        return file_table_from_kb(state[idx]) if idx is not None else pd.DataFrame()

    kb = state[idx]
    for p in paths:
        kb["files"].append({"name": os.path.basename(p), "size": round(os.path.getsize(p) / 1024, 2)})
    gr.Info(f"已向『{kb['name']}』追加 {len(paths)} 个文件")
    return file_table_from_kb(kb)


def recall_test(query, kb_name):
    if not query.strip():
        gr.Warning("请输入查询内容")
        return pd.DataFrame()
    if not kb_name:
        gr.Warning("请选择知识库")
        return pd.DataFrame()

    rows = []
    for i in range(1, 6):
        rows.append({
            "rank": i, "doc": random.choice(["demo_说明.pdf", "requirements.txt"]),
            "score": round(random.random(), 4),
            "snippet": f"『{query}』相关内容片段 #{i}"
        })
    return pd.DataFrame(rows)


# ---------- UI ----------
with gr.Blocks(title="LibRAG") as demo:
    kb_state = gr.State(kb_state_init.copy())
    kb_selected_idx = gr.State(None)

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

            kb_detail_col = gr.Column(visible=False)
            with kb_detail_col:
                kb_files_df = gr.Dataframe(interactive=False, max_height=260)
                add_files_up = gr.File(file_count="multiple", label="追加上传文件", type="filepath")

        # 召回测试tag
        with gr.TabItem("召回测试"):
            with gr.Row():
                query_tb = gr.Textbox(label="输入内容", placeholder="请输入查询…", lines=1, scale=6)
                kb_select_dd = gr.Dropdown(choices=[kb["name"] for kb in kb_state_init],
                                           label="选择知识库", scale=3)
                recall_btn = gr.Button("提交", variant="primary", scale=1)
            recall_df = gr.Dataframe(headers=["rank", "doc", "score", "snippet"],
                                     interactive=False, max_height=350)

    # -- 事件绑定 --
    create_btn.click(lambda: Modal(visible=True), None, create_modal)
    cancel_btn.click(lambda: Modal(visible=False), None, create_modal)
    files_up.change(
        make_preview_cb(),
        inputs=[files_up],  # 只传 uploader
        outputs=[preview_df, *row_comps]  # 行组件放 outputs 控制显隐
    )

    submit_btn.click(
        submit_create_kb,
        inputs=[name_tb, desc_tb, files_up, *dd_inputs],
        outputs=[create_modal, kb_df],
    )

    kb_df.select(
        enter_kb,
        inputs=[kb_state],
        outputs=[kb_selected_idx, kb_detail_col, kb_files_df],
    )

    add_files_up.change(
        add_files_to_kb,
        inputs=[add_files_up, kb_selected_idx, kb_state],
        outputs=kb_files_df,
    )

    recall_btn.click(recall_test, [query_tb, kb_select_dd], recall_df)

# ---------- 启动 ----------
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
