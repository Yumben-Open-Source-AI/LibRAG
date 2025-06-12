import re
from typing import List, Callable
from tools.log_tools import parser_logger as logger
from parser.agentic_chunking import ChunkOrganizer

WHITESPACE_RE = re.compile(r"[ \t\u3000\x0b\x0c\r]+")  # 半角/全角空格、Tab、VT、FF、CR
_SOFT_BREAK = re.compile(r'(?<![。！？!?])\n(?!\n)')
_SENT_END = re.compile(r'[^。！？!?\.]*?(?:[。！？!?]|(?<!\d)\.(?!\d))')

# ========= 1) 原子切分器工厂 ========= #
def char_split(text: str) -> List[str]:
    return list(text)

def sentence_split(text: str) -> List[str]:
    text = _SOFT_BREAK.sub(' ', text)
    text = WHITESPACE_RE.sub(' ', text)
    sentences = [m.group(0).strip() for m in _SENT_END.finditer(text)]
    if not sentences:                       # 全文没句尾 → 整段返回
        sentences = [text.strip()]
    return sentences

def paragraph_split(text: str) -> list[str]:
    # “一个或多个空行（可带列表符/缩进）” 视为段落分隔
    pieces = re.split(r"(?:\n[ \t\-\*\u2022]*\n)+", text, flags=re.MULTILINE)
    # 只保留真正含内容的段落
    return [p.strip() for p in pieces if p.strip()]

SPLITTERS: dict[str, Callable[[str], List[str]]] = {
    "char": char_split,
    "sentence": sentence_split,
    "paragraph": paragraph_split,
}

# ========= 2) 通用递归分割器 ========= #
class FlexibleRecursiveSplitter:
    def __init__(
            self,
            granularity: str = "sentence",
            chunk_size: int = 1024,
            overlap_units: int = 2,
            char_separators: List[str] | None = None,
    ):
        if granularity not in SPLITTERS:
            raise ValueError(f"granularity must be one of {list(SPLITTERS)}")
        self.split_fn = SPLITTERS[granularity]
        self.granularity = granularity
        self.chunk_size = chunk_size
        self.overlap_units = overlap_units
        self.char_separators = char_separators or ["\n\n", "\n", " ","", None]

    # ---- 主入口 ---- #
    def split(self, text: str) -> List[str]:
        text += '.'
        units = self.split_fn(text)
        return self._assemble(units)

    def _join_units(self, units: List[str]) -> str:
        # char 粒度直接拼；其它粒度在单位之间补一个空格
        glue = '' if self.granularity == 'char' else ' '
        return glue.join(units)

    # ---- 组块 + 重叠 ---- #
    def _assemble(self, units: list[str]) -> list[str]:
        chunks, buf, buf_len = [], [], 0
        for u in units:
            logger.debug(f"split unit: {u}")
            u_len = len(u)
            # ---------- A. 超长原子 ----------
            if u_len > self.chunk_size:
                # ① flush 正常缓冲（保留句/段重叠）
                if buf:
                    chunks.append(self._join_units(buf))
                    buf, buf_len = [], 0

                # ② 用 smart_split / 旧 _char_recursive_split 拆超长 u
                parts = self._smart_split(u)  # ← 或 self._char_recursive_split(u)

                if self.granularity == 'char' and self.overlap_units and len(parts) > 1:
                    # ③ 前缀/后缀：取 u 首尾 overlap_units 个「字符」
                    #    - granularity == 'char'  → 刚好是字符级
                    #    - sentence/paragraph    → 只是补一点上下文 glue，不会破坏单位数统计
                    prefix = u[:self.overlap_units]
                    suffix = u[-self.overlap_units:]
                    parts[0] = prefix + parts[0]
                    parts[-1] = parts[-1] + suffix

                chunks.extend(parts)
                continue

            # ---------- B. 正常累积 ----------
            extra = 0 if not buf or self.granularity == 'char' else 1
            if buf_len + u_len + extra <= self.chunk_size:
                buf.append(u)
                buf_len += u_len + extra
            else:
                chunks.append(self._join_units(buf))
                buf = buf[-self.overlap_units:] if self.overlap_units else []
                buf_len = sum(len(x) + (0 if i == 0 or self.granularity == 'char' else 1)
                              for i, x in enumerate(buf))
                extra = 0 if not buf or self.granularity == 'char' else 1
                buf.append(u)
                buf_len += u_len + extra

        if buf:
            chunks.append(self._join_units(buf))
        return [c for c in chunks if c.strip()]

    # 找离 chunk_size 最近的右侧分隔符
    def _smart_split(self, text: str) -> List[str]:
        """把一个超长原子切成若干子串，同时维持不同粒度的重叠。"""
        if len(text) <= self.chunk_size:
            return [text]

        # ① 计算字符 & 单位重叠
        char_overlap = self.overlap_units if self.granularity == "char" else 0
        unit_overlap = self.overlap_units if self.granularity != "char" else 0
        seps = ["\n\n", "\n", " ", ""]  # 最后一个空串 = 硬切

        start, chunks = 0, []
        while start < len(text):
            window_end = min(start + self.chunk_size, len(text))

            # 找离 window_end 最近的分隔符
            cut = None
            for sep in seps:
                idx = text.rfind(sep, start, window_end)
                if idx != -1 and idx > start:
                    cut = idx + len(sep)
                    break
            if cut is None or cut == start:  # 找不到 → 硬切
                cut = window_end

            # 取片段
            chunks.append(text[start:cut])

            # ② 计算下一窗口的起点
            if self.granularity == "char":
                start = max(cut - char_overlap, start + 1)
            else:
                # 句/段模式：尾部再粗分，保留最后 unit_overlap 个单位
                tail_units = (
                    self.split_fn(text[start:cut])[-unit_overlap:]
                    if unit_overlap
                    else []
                )
                tail_len = len(self._join_units(tail_units))
                start = max(cut - tail_len, cut) if tail_len else cut

            # 防止死循环
            if start <= len(chunks[-1]) - self.chunk_size:
                start = cut

        return chunks


if __name__ == "__main__":
    txt = """信息授权书（理财业务版）

尊敬的投资者：
根据《中华人民共和国消费者权益保护法》《中国人民银行金融消费者权益保护实施办法》《商业银行理财业务监督管理办法》《银行保险机构消费者权益保护管理办法》的要求，为了保障您的合法权益，请您在签署本授权书之前，务必审慎阅读本授权书各条款(特别是黑体字条款)，并充分理解授权书条款内容，特别是与您有重大利害关系的条款(包括但不限于被授权人的责任及您的权利有关的条款)，且承诺您具有签订和履行本授权书的资格和能力，同时您签订和履行本授权书不违反您的任何合同义务、职责权限以及相关法律法规的规定。被授权方仅为办理业务所必须之目的收集及处理您的授权信息，如果您不同意相关信息的处理，您可能无法办理需您的相关信息才能办理的业务，但并不影响您正常办理贵阳农商银行其他业务。
一、信息收集
在遵循合法、正当、必要原则的前提下，您在办理理财业务签约、购买理财产品、办理定投等业务时，您授权贵阳农商银行处理您的如下信息：
姓名、身份证号码、银行卡卡号、银行卡有效期、银行预留手机号等与业务办理相关的信息。

二、信息使用
为完整地向您提供服务以及保护各方的合法权益，您理解和同意贵阳农商银行可能会将您的信息用于如下用途：
1.采取密码验证、短信验证码等手段以便于验证您的身份，确保完成理财产品交易。
2.向您提供理财产品信息披露服务，服务内容包括但不限于各类理财产品公告、定期报告以及理财产品账单。
3.为使您知晓贵阳农商银行理财业务情况或向您推荐更优质的理财产品和服务，自行或与供应商合作，通过电子邮件、网络投资者端消息提示或推送、手机短信等方式向您发送产品信息、服务通知、活动或其他商业性电子信息，若您认为前述方式对您造成了打扰，您可以根据本合同提供的客服电话要求退订或在收到相关信息后按照信息提示的方式退订。
4.预防或阻止违法、违规的活动，如识别、打击洗钱等。
5.为维护您的权益(例如预防或阻止非法或危及您人身、财产安全的活动)，或者为了解决服务提供方与您之间的争议。
6.根据法律法规、政府机构、监管部门要求或其他经您另行明确同意的用途。

三、信息提供
贵阳农商银行承诺会根据法律法规及监管规定严格保护您的信息，不会在提供金融服务目的外向第三方披露您的信息，您同意贵阳农商银行可能会在下列情况下将必要的信息提供给第三方，该等第三方将会在贵阳农商银行官方网站上进行公示，您可以在贵阳农商银行官方网站上查询:
1.当向您提供的金融服务需要由贵阳农商银行与第三方共同提供时。
2.用于核实您的身份、处理与您相关的争议、或维护您和/或贵阳农商银行的合法权益的特定情况。
3.向审计机构或审计监管机构提供审计所需的必要信息。
4.根据法律法规、政府机构及其监管部门的要求提供。

四、授权期限
自您签署本授权书之日起，至贵阳农商银行与您的合同义务履行完毕之日止。超过本授权有效期的，为了后续异议或者纠纷处理的需要，从而保障贵阳农商银行及您的合法权益，您同意贵阳农商银行为实现本授权书声明的目的所必须的时限来确定个人信息保存期限，并在此期限内保留个人信息，在留存期限届满后，贵阳农商银行会删除您的信息或采取安全保护措施。法律、行政法规、政府规章、监管规范对投资者个人信息资料有更长保存期限要求的，遵守其规定。

五、信息安全
在使用您信息时，贵阳农商银行会采取必要措施保障信息安全，防止信息非法泄露或不当使用。贵阳农商银行超出本授权范围进行数据查询和使用的一切后果及法律责任由贵阳农商银行自行承担。
六、权利告知
您有权向贵阳农商银行查阅、复制您的个人信息。如果您发现贵阳农商银行收集、使用、保存及对外提供您的信息违反了法律、行政法规及监管文件规定或违反了与您的约定，或您发现贵阳农商银行采集、储存您的信息有误的，您可联系贵阳农商银行要求更正、补充或删除。
如您对上述信息处理与保护条款存在任何疑问，或对于您的个人信息处理存在任何投诉、意见，请通过客服热线0851-96777联系以便为您处理。
七、责任限制
如公安机关、检查机关等执法部门做出了对您不利的决定时，您同意贵阳农商银行无须就此承担责任或赔偿。
八、授权人声明已知悉并理解本授权书所有内容(特别是加粗字体内容)以及由此产生的法律效力，并同意上述条款所载内容。
九、本授权书为纸质的，经您签署后生效；本授权书为电子形式的，经您在贵阳农商银行电子渠道页面上勾选确认后生效。
十、特别提示
□您同意并授权贵阳农商银行会将您的信息用于营销活动、用户体验改进、市场调查，如您需取消相关授权，您可以根据本合同提供的客服电话要求退订或在收到营销信息后按照信息提示的方式退订。
(若您在该条前方框进行勾选，视为您同意.若您不勾选，您可能无法办理需您的相关信息才能办理的业务，但并不影响您正常办理贵阳农商银行其他业务)
您签字或勾选同意，视为您已知晓并同意本《信息授权书》（理财业务版）的全部内容
本人确认：贵阳农商银行已应本授权人要求对所有条款尽了提示、说明、解释义务。本授权是授权人的真实意思表示，本授权人不持任何异议，自愿同意承担由此带来的一切法律后果。

授权人(签名):                                    



















证件号码:                              
证件类型:□身份证□临时身份证□其他                     
授权日期：   年   月   日
授权人(公章)：
法定代表人(负责人或授权代表)：
授权日期：   年   月   日"""
    # A) 段落级 paragraph
    # B) 句子级 sentence
    # C) 字符级 char
    # chunk_size：对小型LLM（上下文2Ktoken）推荐256–512字符；对GPT‑4o等128K‑token窗口可放宽至2K +。
    # granularity：报告 / 合同 → "paragraph"（语义更完整）；FAQ / 问答 → "sentence"（颗粒度适中）；代码 / 超长句边缘 → "char"（兜底）。
    # overlap_units：句级 / 段级通常1‑3；字符级按窗口5–50。

    ps = FlexibleRecursiveSplitter(granularity="paragraph", chunk_size=1024, overlap_units=1)
    import time

    start_time = time.time()
    # organizer = ChunkOrganizer()
    # blocks = []
    # for i, chunk in enumerate(ps.split(txt), 1):
    #     blocks = organizer.process(chunk)
    #     print(f"{i:02d}｜{chunk}")
    print(ps.split(txt))
    end_time = time.time()
    print("程序运行时间：%s 秒" % (end_time - start_time))
