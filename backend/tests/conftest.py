"""**全测试进程**的环境缺省值。⚠️ 本文件刻意**不 import ``app.*`` 里的任何东西**。

--------------------------------------------------------------------------
为什么会有这个文件（Plan 05A Task 1）
--------------------------------------------------------------------------

``tests/api/conftest.py`` 的模块 docstring 逐字写着「本仓的 ``tests/`` 下今天**没有**
根 conftest」，并给了不建它的理由：新建一个会让**全部** 31 个既有测试文件都多一个
导入期依赖（``app.main`` → ``fastapi``），而只有 ``tests/api/`` 与 ``tests/test_main.py``
用得上它。

⚠️ **那条理由对本文件不成立，因为本文件只 import :mod:`os`**。它要做的两件事都是
「在 pytest 收集任何测试**之前**把一个环境变量设好」，而这只有一个住址能做成：
根 conftest 的**模块体**（一个 fixture 做不到——fixture 是 function 级的，
而 :data:`app.auth.passwords.PBKDF2_ITERATIONS` 那两个值要在
``tests/auth/`` / ``tests/api/`` / 任何将来的目录下都生效，逐目录建 conftest
就是把同一份环境事实抄 N 份）。

⚠️ 于是「不建根 conftest」那条纪律**没有被推翻**，它被精确化了：
不要建一个**导入 ``app``** 的根 conftest。本文件的导入面是 ``os`` 一个名字。

--------------------------------------------------------------------------
两个值各自为什么必须是这个数
--------------------------------------------------------------------------

``PE_ALLOW_HEADER_IDENTITY = "1"``
    Plan 05A 的**双通道过渡**（计划 §2.1）。既有 **1270 条**测试与 ``smoke.mjs`` 的
    16 步全部假设「请求头传身份」，而它们验的是**业务规则**、不是鉴权；
    生产缺省是 ``"0"``（只认 cookie 会话），故测试进程必须显式打开那一档，
    否则 1270 条会全部撞 401。
    ⚠️ **这不是「把守卫调松」**：``"0"`` 那一档由
    ``tests/api/test_auth_api.py`` 的
    ``test_the_header_identity_channel_is_closed_by_default`` 单独钉住
    （``monkeypatch.delenv`` 之后**重建 app**，断言匿名带 ``X-Student-Id: 1``
    读 ``/api/students/1/home`` 是 **401**）。少了那条守卫，
    「生产忘了设这个变量、于是谁都能伪造请求头」是**静默**的。

``PBKDF2_ITERATIONS = "1000"``
    生产缺省是 **600 000**（OWASP 2023 对 PBKDF2-SHA256 的建议值），一次哈希 ~0.3 s。
    测试里有几十条碰口令，按生产值跑会把套件从 2 分钟拖到半小时。
    ⚠️ **而「调低了忘了调回来」是静默的**（生产上只是登录慢一点，没有测试会红），
    故 ``tests/auth/test_passwords.py`` 的
    ``test_the_production_default_iterations_is_at_least_the_owasp_floor``
    钉的是 :data:`app.auth.passwords.PBKDF2_DEFAULT_ITERATIONS` 那个**字面量**
    （不是 ``iterations()`` 的返回值），并另外用 ``monkeypatch.delenv`` 钉住
    「环境变量没设时解析函数**就是**那个字面量」。

⚠️ 两处都用 :func:`os.environ.setdefault` 而不是直接赋值：
外面显式设过的值（例如 CI 上按生产值跑一次口令测试）应当胜出，
而直接赋值会让「显式设了」与「没设」在测试里无法区分。
"""
import os

os.environ.setdefault("PE_ALLOW_HEADER_IDENTITY", "1")
os.environ.setdefault("PBKDF2_ITERATIONS", "1000")
