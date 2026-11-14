"""Optional demo data for local visual checks.

Run from backend/:
    .\\venv\\Scripts\\python.exe seed_demo.py
It is safe to run once on a fresh development database.
"""
from __future__ import annotations

import io
import os
from datetime import timedelta

import django
from PIL import Image, ImageDraw, ImageFilter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.core.files.base import ContentFile  # noqa: E402
from django.utils import timezone  # noqa: E402

from agent.models import Conversation, Message  # noqa: E402
from chat.models import ChatMessage  # noqa: E402
from transfer.models import TransferFile  # noqa: E402


def gradient_image(width: int, height: int, colors: tuple[str, str, str]) -> bytes:
    base = Image.new("RGB", (width, height), "#0b1220")
    draw = ImageDraw.Draw(base)
    for y in range(height):
        for_x = y / max(height - 1, 1)
        r = int(20 + (54 - 20) * for_x)
        g = int(30 + (94 - 30) * for_x)
        b = int(60 + (190 - 60) * for_x)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((width * 0.52, -height * 0.28, width * 1.2, height * 0.7), fill=colors[0])
    od.ellipse((-width * 0.18, height * 0.48, width * 0.6, height * 1.25), fill=colors[1])
    od.ellipse((width * 0.22, height * 0.18, width * 0.52, height * 0.6), fill=colors[2])
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=38))
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")

    d = ImageDraw.Draw(base)
    d.rounded_rectangle(
        (36, 36, width - 36, height - 36),
        radius=26,
        outline=(255, 255, 255, 42),
        width=1,
    )
    d.ellipse((58, 58, 80, 80), fill=(255, 255, 255))
    for index in range(5):
        d.rounded_rectangle(
            (58, height - 118 + index * 15, width - 120 - index * 34, height - 112 + index * 15),
            radius=3,
            fill=(255, 255, 255, 40 + index * 20),
        )
    buffer = io.BytesIO()
    base.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def make_pdf() -> bytes:
    try:
        import pymupdf
    except ImportError:  # pragma: no cover
        return b"%PDF-1.4\n% demo\n%%EOF"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 92), "zixxx - Project Brief", fontsize=20)
    page.insert_text((72, 130), "Self-hosted multimodal AI workspace", fontsize=11)
    document.save("/tmp/zixxx_demo.pdf") if False else None
    data = document.tobytes()
    document.close()
    return data


def add_transfer(name: str, data: bytes, mime: str, public: bool, uploader: str, remark: str, age_hours: int):
    record = TransferFile(
        original_name=name,
        file_size=len(data),
        file_type=mime,
        remark=remark,
        is_public=public,
        uploader_name=uploader,
    )
    record.file.save(name, ContentFile(data), save=True)
    TransferFile.objects.filter(pk=record.pk).update(
        created_at=timezone.now() - timedelta(hours=age_hours)
    )
    return record


def main() -> None:
    if TransferFile.objects.exists() or ChatMessage.objects.exists():
        print("Demo data already exists; nothing to do.")
        return

    image = gradient_image(
        900,
        560,
        (
            (240, 106, 156, 160),
            (34, 211, 238, 105),
            (129, 140, 248, 130),
        ),
    )
    image2 = gradient_image(
        760,
        460,
        (
            (251, 191, 36, 120),
            (96, 165, 250, 100),
            (167, 139, 250, 130),
        ),
    )
    add_transfer(
        "aurora-preview.png",
        image,
        "image/png",
        True,
        "免密访客",
        "新一版配色预览，欢迎直接下载",
        3,
    )
    add_transfer(
        "zixxx-项目说明.pdf",
        make_pdf(),
        "application/pdf",
        True,
        "免密访客",
        "项目背景与模块划分",
        20,
    )
    add_transfer(
        "design-notes.txt",
        "Aurora preview\n\n- 降低蓝色饱和度\n- 增加留白\n- 保留高对比标题\n".encode(),
        "text/plain",
        True,
        "qzx",
        "给 sqx 的设计备注",
        27,
    )
    add_transfer(
        "handover-secret.png",
        image2,
        "image/png",
        False,
        "免密访客",
        "私密投递：周末交接用",
        1,
    )
    add_transfer(
        "只有-qzx-可见.txt",
        "这是一份只对 qzx 可见的私密文件。\n访客列表中不会出现。".encode(),
        "text/plain",
        False,
        "免密访客",
        "私密说明",
        5,
    )

    su = User.objects.get(username="sqx")
    qzx = User.objects.get(username="qzx")
    # Chat pair is qzx ↔ sqx; `zi` keeps the demo spec variable naming.
    zi = qzx

    now = timezone.now()
    chat_specs = [
        (zi, su, "text", "我刚把设计稿放到中转站了，公开的那份你可以直接看。", None, None, 46),
        (su, zi, "text", "看到了，颜色比上一版干净很多。", None, None, 44),
        (zi, su, "file", "这一版把蓝色收了一点。", image, "aurora-preview.png", 40),
        (su, zi, "text", "收到，晚点我把反馈发你。", None, None, 37),
        (zi, su, "text", "不急，记得先吃饭。", None, None, 36),
    ]
    for index, (sender, recipient, kind, content, data, filename, hours) in enumerate(chat_specs):
        message = ChatMessage.objects.create(
            sender=sender,
            recipient=recipient,
            message_type=kind,
            content=content,
            file_name=filename or "",
            file_size=len(data) if data else 0,
            file_type="image/png" if data else "",
        )
        if data and filename:
            message.file.save(filename, ContentFile(data), save=False)
            message.save()
        ChatMessage.objects.filter(pk=message.pk).update(
            created_at=now - timedelta(hours=hours, minutes=index * 3)
        )

    conversation = Conversation.objects.create(
        user=qzx,
        title="傅里叶变换：从直觉到代码",
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1, minutes=30),
    )
    user_text = "我想真正理解傅里叶变换。能不能从直觉开始，再给一个可运行的 Python 示例？"
    assistant_text = """傅里叶变换的出发点其实很朴素：**任何复杂信号，都可以看成许多不同频率的简单波叠加。**

## 1. 它在做什么？

对一个随时间变化的信号 $f(t)$，连续傅里叶变换写作：

$$
F(\\omega)=\\int_{-\\infty}^{\\infty} f(t)\\,e^{-i\\omega t}\\,dt
$$

可以把 $e^{-i\\omega t}$ 想成一根以角频率 $\\omega$ 旋转的指针。积分则是在问：*信号中究竟含有多少这个节奏？*

> **关键直觉**：时域告诉你“何时发生”，频域告诉你“由哪些节奏组成”。

## 2. 三个容易混淆的概念

| 概念 | 输入 | 输出 | 直觉 |
| :--- | :--- | :--- | :--- |
| 傅里叶级数 | 周期信号 | 离散谐波 | 用有限的音叉拼出周期波 |
| 连续傅里叶变换 | 连续非周期信号 | 连续频谱 | 用无限多音叉拼出任意波 |
| DFT / FFT | 离散采样点 | 离散频点 | 计算机真正执行的版本 |

## 3. 一个可运行的例子

下面用 FFT 分解一个“两个正弦波叠加”的信号：

```python
import numpy as np
import matplotlib.pyplot as plt

sample_rate = 1000
duration = 1.0
t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

# 5 Hz 基波 + 20 Hz 谐波
signal = 0.8 * np.sin(2 * np.pi * 5 * t) + 0.35 * np.sin(2 * np.pi * 20 * t)

spectrum = np.fft.rfft(signal)
freqs = np.fft.rfftfreq(len(signal), d=1 / sample_rate)
amplitude = np.abs(spectrum) / len(signal)

peaks = freqs[np.argsort(amplitude)[-3:]]
print("主要频率:", np.round(np.sort(peaks), 2))
```

运行后应当看到 **5 Hz** 与 **20 Hz** 两个尖峰。其余接近零的频点，就是“没有这个节奏”的数学表达。

## 4. 为什么它在工程里无处不在？

- **音频**：均衡器本质上是在调整不同频段的增益。
- **图像**：频域滤波可以去除规则噪声，也能做模糊与锐化。
- **通信**：OFDM 把许多子载波正交地叠在一起传输数据。

如果你愿意，我下一步可以带你从 **DFT 的矩阵形式** 推导 FFT，或者用一张动图拆解“旋转指针”的直觉。"""
    assistant_summary = """用三句话总结：

1. **分解**：傅里叶变换把复杂信号拆成不同频率的正弦 / 复指数成分。
2. **测量**：频谱中的每个值，表示原信号在对应频率上的“含量”与相位。
3. **计算**：工程中通常使用离散的 DFT，并用 FFT 在 $O(N\\log N)$ 时间内完成计算。"""
    messages = [
        ("user", user_text, now - timedelta(hours=2)),
        ("assistant", assistant_text, now - timedelta(hours=1, minutes=57)),
        ("user", "再把它总结成三句话。", now - timedelta(hours=1, minutes=35)),
        ("assistant", assistant_summary, now - timedelta(hours=1, minutes=30)),
    ]
    for role, content, created in messages:
        message = Message.objects.create(
            conversation=conversation, role=role, content=content
        )
        Message.objects.filter(pk=message.pk).update(created_at=created)

    print("Demo data created:")
    print("  transfer files:", TransferFile.objects.count())
    print("  chat messages:", ChatMessage.objects.count())
    print("  agent messages:", Message.objects.count())


if __name__ == "__main__":
    main()