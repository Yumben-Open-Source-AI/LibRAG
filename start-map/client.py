"""
Knowledge‑Base Manager & Recall‑Test Demo
Gradio 5.25.2  +  gradio_modal ≥0.2
"""

import os, random, functools, inspect, logging, pprint
import gradio as gr
import pandas as pd
from gradio_modal import Modal

# ============ 日志装饰器（打印所有输入 / 输出） ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


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


# ---------- 工具函数 ----------
def kb_table_from_state(state):
    return pd.DataFrame(
        [{"知识库名称": kb["name"], "文件数": len(kb["files"])} for kb in state]
    )


def file_table_from_kb(kb):
    return pd.DataFrame(kb["files"]) if kb else pd.DataFrame()


# ---------- 回调 ----------
@log_io
def preview_upload(paths):
    rows = [
        {"文件名": os.path.basename(p), "大小(KB)": round(os.path.getsize(p) / 1024, 2)}
        for p in paths or []
    ]
    return pd.DataFrame(rows, columns=["文件名", "大小(KB)"])


@log_io
def submit_create_kb(name: str, paths: list[str], state: list[dict]):
    if not name.strip():
        gr.Warning("知识库名称不能为空")
        return state, kb_table_from_state(state), None, pd.DataFrame(), gr.update(
            choices=[kb["name"] for kb in state]), Modal(visible=False)

    if not paths:
        gr.Warning("请选择至少一个文件")
        return state, kb_table_from_state(state), None, pd.DataFrame(), gr.update(
            choices=[kb["name"] for kb in state]), Modal(visible=False)

    files_meta = [{"name": os.path.basename(p), "size": round(os.path.getsize(p) / 1024, 2)} for p in paths]
    state.append({"name": name.strip(), "files": files_meta})
    gr.Info(f"知识库『{name}』已创建，共 {len(paths)} 个文件")

    updated_table = kb_table_from_state(state)
    dd_choices = [kb["name"] for kb in state]

    return state, updated_table, None, pd.DataFrame(), gr.update(choices=dd_choices), Modal(visible=False)


@log_io
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


@log_io
def add_files_to_kb(paths, idx, state):
    if idx is None or idx >= len(state) or not paths:
        return file_table_from_kb(state[idx]) if idx is not None else pd.DataFrame()

    kb = state[idx]
    for p in paths:
        kb["files"].append({"name": os.path.basename(p), "size": round(os.path.getsize(p) / 1024, 2)})
    gr.Info(f"已向『{kb['name']}』追加 {len(paths)} 个文件")
    return file_table_from_kb(kb)


@log_io
def recall_test(query, kb_name):
    if not query.strip():
        gr.Warning("请输入查询内容")
        return pd.DataFrame()
    if not kb_name:
        gr.Warning("请选择知识库")
        return pd.DataFrame()
    rows = [
        {"rank": i, "doc": random.choice(["demo_说明.pdf", "requirements.txt"]),
         "score": round(random.random(), 4),
         "snippet": f"『{query}』相关内容片段 #{i}"} for i in range(1, 6)
    ]
    return pd.DataFrame(rows)


# ---------- UI ----------
with gr.Blocks(title="KB Manager & Recall Test") as demo:
    kb_state = gr.State(kb_state_init.copy())
    kb_selected_idx = gr.State(None)

    with gr.Tabs(selected=0):
        with gr.TabItem("知识库管理"):
            with gr.Row():
                create_btn = gr.Button("创建知识库", variant="primary")
                kb_df = gr.Dataframe(
                    value=kb_table_from_state(kb_state_init),
                    interactive=False,
                    max_height=260,
                )

            create_modal = Modal(visible=False)
            with create_modal:
                gr.Markdown("### 创建新知识库")
                name_tb = gr.Textbox(label="知识库名称")
                files_up = gr.File(file_count="multiple", label="上传文件（多选）", type="filepath")
                preview_df = gr.Dataframe(interactive=False, max_height=150)
                with gr.Row():
                    submit_btn = gr.Button("提交", variant="primary")
                    cancel_btn = gr.Button("取消")

            kb_detail_col = gr.Column(visible=False)
            with kb_detail_col:
                kb_files_df = gr.Dataframe(interactive=False, max_height=260)
                add_files_up = gr.File(file_count="multiple", label="追加上传文件", type="filepath")

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
    files_up.change(preview_upload, files_up, preview_df)

    submit_btn.click(
        submit_create_kb,
        inputs=[name_tb, files_up, kb_state],
        outputs=[kb_state, kb_df, files_up, preview_df, kb_select_dd, create_modal],
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
