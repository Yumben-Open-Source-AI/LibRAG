import os
from typing import List, Union


class TextFileReader:
    """
    读取项目内.txt文件内容并返回原始格式数据的工具类

    功能：
    - 自动处理文件路径（相对/绝对路径）
    - 支持多种编码格式（默认UTF-8）
    - 保留原始换行符和空白字符
    - 自动关闭文件资源
    """

    def __init__(self, base_dir: str = None):
        """
        初始化读取器
        :param base_dir: 项目根目录路径（默认为当前工作目录）
        """
        self.base_dir = base_dir or os.getcwd()

    def read_file(self, file_path: str, encoding: str = 'utf-8') -> Union[str, List[str]]:
        """
        读取.txt文件内容
        :param file_path: 文件路径（相对或绝对）
        :param encoding: 文件编码（默认UTF-8）
        :return: 原始文件内容（字符串或行列表）
        """
        # 构建完整文件路径
        full_path = os.path.join(self.base_dir, file_path) if not os.path.isabs(file_path) else file_path

        try:
            with open(full_path, 'r', encoding=encoding) as file:
                # 读取整个文件内容（保留所有格式）
                content = file.read()
                return content
        except UnicodeDecodeError:
            # 尝试其他常见编码
            encodings = ['gbk', 'latin-1', 'utf-16']
            for enc in encodings:
                try:
                    with open(full_path, 'r', encoding=enc) as file:
                        return file.read()
                except UnicodeDecodeError:
                    continue
            raise ValueError(f"无法解码文件 {file_path}，尝试的编码：UTF-8, GBK, Latin-1, UTF-16")
        except FileNotFoundError:
            raise FileNotFoundError(f"文件未找到：{full_path}")
        except Exception as e:
            raise RuntimeError(f"读取文件时出错：{str(e)}")

    def read_lines(self, file_path: str, encoding: str = 'utf-8') -> List[str]:
        """
        按行读取文件内容（保留行尾换行符）
        :param file_path: 文件路径
        :param encoding: 文件编码
        :return: 包含每行内容的列表
        """
        full_path = os.path.join(self.base_dir, file_path) if not os.path.isabs(file_path) else file_path

        with open(full_path, 'r', encoding=encoding) as file:
            return file.readlines()  # 保留每行末尾的\n