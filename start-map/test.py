"""
@Project ：start-map
@File    ：test2.py
@IDE     ：PyCharm
@Author  ：XMAN
@Date    ：2025/4/23 下午5:22
"""
"""
Knowledge-Base Manager & Recall-Test Demo
Gradio 5.25.2  +  gradio_modal ≥0.2
"""

import os, random, functools, inspect, logging, pprint, pandas as pd
import gradio as gr
from gradio_modal import Modal
from tools.http_utils import RequestHandler           # ← 你的后端工具

# ----------------------- 全局配置 ----------------------- #
ALL_STRATEGY = {
    "按页切割": "page_split",
    "按目录切割": "catalog_split",
    "智能上下文切割": "automate_judgment_split",
}
MAX_ROWS = 20             # 预留最多 20 行“文件✕策略”

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

def log_io(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        bound = dict(zip(inspect.getfullargspec(fn).args, a)) | kw
        logging.info(f"[CALL] {fn.__name__} → {pprint.pformat(bound, compact=True)}")
        res = fn(*a, **kw)
        logging.info(f"[RETURN] {fn.__name__} ← {pprint.pformat(res, compact=True)}")
        return res
    return wrapper

# ----------------------- 数据层 ----------------------- #
def get_kb_table():
    """从后端接口拉现有知识库列表"""
    all_kbs = RequestHandler("http://127.0.0.1:13113/ai/").safe_send_request(
        "knowledge_bases", "GET"
    )
    return pd.DataFrame(
        [{"已有知识库名称": kb["kb_name"], "已有知识库描述": kb["kb_description"]} for kb in all_kbs]
    )

def file_table_from_kb(kb):        # 进入知识库时展示文件列表
    return pd.DataFrame(kb["files"]) if kb else pd.DataFrame()

kb_state_init = [{
    "name": "DemoKB",
    "files": [
        {"name": "demo_说明.pdf", "size": 123.4},
        {"name": "requirements.txt", "size": 2.7},
]}]

# ----------------------- 回调 ----------------------- #
def make_preview_cb(row_comps):
    """闭包：动态控制行显隐 + 预览表格"""
    @log_io
    def preview_upload(paths):
        # 1) 生成右下 DataFrame 预览
        df = pd.DataFrame([
            {"文件名": os.path.basename(p),
             "大小(KB)": round(os.path.getsize(p)/1024, 2),
             "文件类型": os.path.splitext(p)[1][1:]}
            for p in (paths or [])
        ])
        # 2) 更新行组件
        updates = []
        for i in range(MAX_ROWS):
            row, tb, dd = row_comps[i*3:(i+1)*3]
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

@log_io
def submit_create_kb(name, desc, paths, *strategies, state):
    """保存知识库 + 每个文件的切割策略"""
    if not name.strip():
        gr.Warning("知识库名称不能为空"); return state, Modal(visible=True)
    if not desc.strip():
        gr.Warning("知识库描述不能为空"); return state, Modal(visible=True)
    if not paths:
        gr.Warning("请选择至少一个文件"); return state, Modal(visible=True)

    files_meta = []
    for p, dd in zip(paths, *strategies):
        files_meta.append({
            "name": os.path.basename(p),
            "size": round(os.path.getsize(p)/1024, 2),
            "strategy": ALL_STRATEGY.get(dd, "automate_judgment_split")
        })

    # —— 持久化到后端：此处只示例本地 state —— #
    state.append({"name": name.strip(), "desc": desc.strip(), "files": files_meta})
    gr.Info(f"知识库『{name}』已创建，共 {len(paths)} 个文件")
    return (
        state,                               # 更新状态
        Modal(visible=False),                # 关闭弹窗
        get_kb_table()                       # 刷新左侧总表
    )

# 进入知识库行后，展开文件列表
@log_io
def enter_kb(evt: gr.SelectData, state):
    idx = evt.index if isinstance(evt.index, int) else evt.index[0]
    if idx is None or idx >= len(state): return None, gr.Dataframe()
    return idx, file_table_from_kb(state[idx])

# ----------------------- 构建 UI ----------------------- #
with gr.Blocks(title="LibRAG") as demo:
    kb_state = gr.State(kb_state_init.copy())
    kb_selected_idx = gr.State(None)

    with gr.Tabs(selected=0):
        # -------- Tab1: 知识库管理 --------
        with gr.TabItem("知识库管理"):
            with gr.Row():
                kb_df = gr.Dataframe(value=get_kb_table, interactive=False, max_height=260)
                create_btn = gr.Button("创建知识库", variant="primary")

            # ---- 创建知识库 Modal ----
            create_modal = Modal(visible=False)
            with create_modal:
                gr.Markdown("### 创建新知识库")
                name_tb = gr.Textbox(label="知识库名称")
                desc_tb = gr.Textbox(label="知识库描述")

                with gr.Row():
                    # 左边：多文件上传
                    files_up = gr.File(file_count="multiple", type="filepath",
                                       label="上传文件（多选）", scale=4)

                    # 右边：动态“文件名 + 策略”表
                    with gr.Column(scale=5):
                        row_comps, dd_inputs = [], []
                        for i in range(MAX_ROWS):
                            with gr.Row(visible=False) as r:
                                tb = gr.Textbox(label=f"文件{i+1}")
                                dd = gr.Dropdown(list(ALL_STRATEGY.keys()), label="切割策略")
                            row_comps.extend([r, tb, dd])
                            dd_inputs.append(dd)  # 仅 dropdown 需要读值

                # 下方：文件预览 DataFrame
                preview_df = gr.Dataframe(interactive=False, max_height=150)

                with gr.Row():
                    submit_btn = gr.Button("提交", variant="primary")
                    cancel_btn = gr.Button("取消")

            # ---- 右侧知识库详情 ----
            with gr.Column():
                kb_files_df = gr.Dataframe(interactive=False, max_height=260)

        # -------- Tab2: 召回测试（保留原逻辑，可按需扩展） --------
        with gr.TabItem("召回测试"):
            query_tb = gr.Textbox(label="输入内容", lines=1)
            kb_select_dd = gr.Dropdown(choices=[kb["name"] for kb in kb_state_init],
                                       label="选择知识库")
            recall_btn = gr.Button("查询")
            recall_df = gr.Dataframe(headers=["rank", "doc", "score", "snippet"],
                                     interactive=False, max_height=350)
    # ----------------- 事件绑定 ----------------- #
    create_btn.click(lambda: Modal(visible=True), None, create_modal)
    cancel_btn.click(lambda: Modal(visible=False), None, create_modal)

    # uploader → 行组件 + 预览 DataFrame
    preview_upload = make_preview_cb(row_comps)
    files_up.change(
        preview_upload,
        inputs=[files_up],               # 只传 uploader
        outputs=[preview_df, *row_comps] # 行组件放 outputs 控制显隐
    )

    # 提交新知识库
    submit_btn.click(
        submit_create_kb,
        inputs=[name_tb, desc_tb, files_up, *dd_inputs, kb_state],
        outputs=[kb_state, create_modal, kb_df],
    )

    # 左侧总表选中 → 右侧文件列表
    kb_df.select(enter_kb,
                 inputs=[kb_state],
                 outputs=[kb_selected_idx, kb_files_df])

# ----------------------- 启动 ----------------------- #
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)

