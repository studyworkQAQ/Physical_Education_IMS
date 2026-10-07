"""``app.domain.prescription`` 的公开面：从这里重导出，消费者不必记住内部模块划分。

计划的 File Structure 把本文件列为「公开面重导出」（Plan02 账本 P2-B1 指出原文没有任何
Task 的 Files 段认领它，而没有它这个包不成立，故归 Task 2）。

**逐 Task 递增**：本 Task 只重导出 :class:`ImpactLevel`，因为 ``templates.py`` 今天也只有
它（P2-B1）。Task 3 往 ``templates.py`` / ``match.py`` 加东西、Task 5–9 各自建自己的模块
时，请同步往这里与 ``__all__`` 追加——两处必须一起改，否则 ``__all__`` 会谎报公开面。
"""
from .templates import ImpactLevel

__all__ = ["ImpactLevel"]
