import time
import os
import psutil
import pyautogui
import pygetwindow as gw
import pyperclip


def wps_pdf_to_txt(pdf_path, txt_path, wait_time=5):
    """通过WPS Office复制PDF内容"""
    try:
        # 清空剪贴板
        pyautogui.hotkey('ctrl', 'c')  # 清空可能存在的残留内容
        time.sleep(1)

        # 使用WPS打开PDF
        os.startfile(pdf_path)
        print("等待WPS PDF阅读器启动...")

        # 窗口激活检测（适配WPS多语言版本）
        wps_window = None
        for _ in range(20):
            # 查找包含"PDF"或"WPS"的窗口
            for win in gw.getAllWindows():
                if "PDF" in win.title or "WPS" in win.title:
                    wps_window = win
                    break
            if wps_window:
                wps_window.activate()
                wps_window.maximize()  # 最大化窗口
                time.sleep(2)
                break
            time.sleep(1)
        else:
            raise Exception("WPS窗口未找到")

        # WPS专用操作流程
        pyautogui.click(300, 300)  # 点击文档区域确保焦点
        time.sleep(1)

        # 执行全选复制（WPS可能需要两次全选操作）
        for attempt in range(3):
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'a')  # WPS有时需要二次确认
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(1)

            # 获取剪贴板内容
            content = pyperclip.paste()  # 关键修改点
            if len(content.strip()) > 50:  # 提高有效性验证阈值
                break
            print(f"第 {attempt + 1} 次重试...")
        else:
            raise Exception("无法获取有效内容")

        # 写入文件（处理WPS的换行符问题）
        with open(txt_path, 'w', encoding='utf-8') as f:
            cleaned_content = content.replace('\x0c', '\n')  # 处理WPS的特殊换页符
            f.write(cleaned_content)

        print(f"成功保存 {len(content)} 字符到 {txt_path}")

    finally:
        # 关闭WPS进程
        time.sleep(1)
        pyautogui.hotkey('alt', 'f4')  # 关闭窗口
        kill_wps_processes()


def kill_wps_processes():
    """终止WPS相关进程"""
    targets = ['wps.exe', 'wpspdf.exe', 'et.exe']
    for proc in psutil.process_iter():
        try:
            if proc.name().lower() in targets:
                proc.kill()
        except Exception:
            continue


# 使用示例
wps_pdf_to_txt(r"D:\xqm\python\project\llm\start-map\files\比亚迪股份有限公司 2024年第三季度报告（2024-10-30）.pdf",
               "output.txt", wait_time=7)
