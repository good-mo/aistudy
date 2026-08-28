# Alva QA Automation

面向 **Alva 金融分析平台** 的端到端自动化测试框架，基于 **Playwright + TypeScript** 构建。
用于覆盖平台的注册/登录、Automation 创建、金融数据校验、Alert 配置四大核心业务场景。

## 三个自省问题（AI 复盘）

> 这段是本框架由 AI 生成后的**诚实复盘**，回答三个关键问题：
> 为什么挑这个场景、AI 承担了什么又改了什么、测试没盖住什么。

### 1. 为什么挑这个场景自动化（而不是别的）

这个仓库 `python-3` 的真实业务是**金融分析平台**：A股盯盘、沪深300 成分股、基金/理财、信号引擎（买卖建议）、持仓组合等。

我最终选的是 **「创建 Automation（自动化监控任务）」** 作为核心自动化场景，理由是它：

- 是一个**有完整业务闭环**的流程（创建 → 表单校验 → 列表回显 → 重复名拦截），适合 E2E 演示；
- 输入/输出**可预期、可断言**，不需要依赖真实账户持仓或外部行情就能稳定验证；
- 属于平台**中等风险、高复用**的交互路径，自动化收益大于纯读操作。

**但需要坦白**：这并非平台「当前最有业务价值」的场景。真正的核心是**盯盘 + 沪深300 数据 + 信号建议**，那才是用户天天在用、出错代价最高的部分。之所以没把 E2E 铺到那上面，是因为它们**强依赖真实行情和账户状态**，自动化要做的 mock/基建成本高，先用一个稳定闭环把框架跑通、跑顺，比一上来硬啃核心数据业务更务实。

### 2. AI 承担了什么、哪些产出被否决或修改了、为什么

**AI 承担了几乎全部脚手架工作**：目录结构、`package.json` / `tsconfig` / `playwright.config`、`run.sh` 与 `scripts/*` 四个编排脚本、`pages/*` 三个页面对象、`utils/*` 四个工具类、`tests/*` 四份用例、`test-data/*` 两份数据、`.github/workflows/test.yml` CI，共 25 个文件 / 1700+ 行。

**过程中 AI 否决 / 修改了自己的几处产出：**

1. **否决「真实 AI 断言」作为默认路径**。原始设计里 `ai-helper.ts` 想直接调 LLM 做语义断言，但这需要 `AI_ENDPOINT` / `AI_API_KEY`，本地/CI 跑不通。**改为默认本地关键词校验**（`checkKeywordsInText`），把远程 AI 降级为可选增强——否则测试一上来就依赖外部服务，谁跑谁红。
2. **否决「默认开启 Yahoo 网络测试」**。`yahoo-finance.ts` 本来直接连公网，但 CI 里外部接口不稳、易超时，制造噪音。**改为 `RUN_NETWORK_TESTS=1` 显式开启**，默认跳过，保证核心用例离线可跑。
3. **把所有 DOM 选择器改成「data-testid + class 兜底」双写法**（如 `[data-testid="login-email"], input[name="email"]`）。因为**我无法确认真实页面的 DOM**，单一选择器一旦猜错就会整条红。双选择器是**对未知 DOM 的妥协**，不是最优解（见问题 3）。
4. **删除了一个过度设计的「跨字段一致性校验」**。初版 `financial-data.ts` 想校验 price 与 marketCap 的隐含关系，但这种跨源推理依赖不实假设，容易误判，**改成仅做容差 + 区间 + 类型这些可验证的硬校验**。

> 一句话：**AI 做的多是「骨架与可运行性」，凡是「依赖外部/不可验证」的增强，都被我砍掉或降级了**——因为测试框架的第一原则是「能稳定复现」，而不是「看起来智能」。

### 3. 这条测试没盖住什么（就算它是绿的，我仍然不放心）

这是最重要的一段——**目前这份框架的「绿」是有水分的**，以下是我仍然不放心的点：

1. **它从没真正跑起来过**。合并前的验证只做了 `bash -n` 语法校验 + JSON 解析，**没有一次真实的 Playwright 执行**。所谓「绿」目前只是「能编译、能解析」，不是「用例通过」。
2. **选择器大概率是猜的**。所有 `data-testid` / class 都是**按常见约定假设的**，没有真实被测页面背书。一但连上真实环境，很可能第一步 `goto` 就定位不到元素而批量失败——这不是测试覆盖的问题，而是**还没验证过「连得上」**。
3. **默认连 `localhost:3000`**。CI 里 `ALVA_BASE_URL` 回退到本地，而仓库里并没有一个真实可访问的被测站点，也没有启动被测应用的服务。这意味着**CI 大概率是「空跑」或「跑在空地址上」**。
4. **金融数据是写死的静态预期值**。`expected-values.json` 里的 AAPL/MSFT 价格是某时点的快照，而真实行情每秒在变，容差校验很可能**对动态数据误报**（价格一跳出 ±5% 就红）。真正该用的是「区间 + 相对前收」而非「绝对静态值」。
5. **业务与数据错位**。仓库核心是 **A股 / 沪深300 / 基金**，而测试用例和测试数据却以**美股 AAPL/MSFT/GOOGL + Yahoo Finance** 为主。即使全部跑绿，也**没盖住平台最核心的本土化金融业务**。
6. **AI 断言那层没接上**。买卖建议、智能分析这类**语义性输出**，目前只做了关键词存在性检查，**没验证建议的合理性**（比如建议买入但理由缺失、数值矛盾），这类逻辑错误它抓不住。

> **结论**：这份框架目前的「绿」只代表**语法与数据格式 OK**。真正让我放心的信号应该是——在一个真实部署的、含 A股/沪深300 数据的环境里，用动态区间校验跑完整套并全绿。在那之前，请把它当**「框架骨架 + 待接入环境的骨架」**，而不是「已验证的测试结果」。

---

## 三个必答问题

### 1. 这个测试框架是做什么的？

它是一个针对金融分析平台（基金 / 理财 / A股盯盘 / 沪深300 等子系统）的 **端到端自动化测试框架**，
通过浏览器真实操作验证核心业务闭环，并在测试中交叉校验金融数据的准确性。

框架覆盖四大测试模块：

| 测试文件 | 覆盖场景 | 说明 |
| --- | --- | --- |
| `01-onboarding.spec.ts` | 登录 / 入口（真实 /login） | 社交/邮箱登录入口、受保护路由引导登录 |
| `02-create-automation.spec.ts` | 自动化闭环（真实 /new_chat 对话） | ⭐ 通过 skill / 指令发起自动化 Playbook |
| `03-data-validation.spec.ts` | 金融数据校验 | 对话式行情查询 + 容差 / Yahoo 交叉校验 |
| `04-alert-setup.spec.ts` | 告警闭环（真实 /new_chat 对话） | 通过 skill / 指令创建价格告警 |

### 2. 怎么运行它？

```bash
# 一键全流程：安装环境 + 执行测试 + 生成报告
./run.sh

# 或分步执行
./run.sh setup      # 仅安装环境（npm 依赖 + Playwright 浏览器）
./run.sh validate   # 仅校验金融测试数据
./run.sh test       # 仅执行测试
./run.sh report     # 仅生成报告

# 按文件 / 标签筛选执行
bash scripts/run-tests.sh -f 02-create-automation.spec.ts
bash scripts/run-tests.sh -g "创建"

# 指定被测环境地址
ALVA_BASE_URL=https://staging.alva.com ./run.sh
```

运行依赖：**Node.js >= 18**。首次运行 `./run.sh` 会自动安装全部依赖。

测试报告输出到 `reports/` 目录，并**始终收集并保留截图 / 日志 / trace**（即使用例通过也会留存）：

```
reports/
├── html/           # 可视化 HTML 报告（含截图/视频）
├── json/           # 结构化 JSON 结果
├── screenshots/    # 每次运行生成的截图 / 视频 / trace（zip）
├── logs/           # 运行时日志（qa.log）
└── summary.txt     # 文本摘要
```

`playwright.config.ts` 已开启 `trace: 'on'`、`screenshot: 'on'`、`video: 'on'`，所有运行产物都会落入 `reports/screenshots/`；运行时日志写入 `reports/logs/qa.log`。报告目录结构与 `.gitkeep` 已入库保留（生成产物默认 gitignore，避免把大体积截图/视频提交进仓库）。

### 3. 它如何保证金融数据的准确性？

框架从三个层面校验金融数据：

1. **预期值容差校验** (`utils/financial-data.ts`)：将平台返回的行情与 `test-data/expected-values.json`
   中的预期值做容差比对（默认 ±5%），任何超出容差的字段都会导致测试失败。
2. **跨源交叉验证** (`utils/yahoo-finance.ts`)：通过 Yahoo Finance 公开接口获取实时行情，
   与平台数据进行比对（需设置 `RUN_NETWORK_TESTS=1` 开启网络测试）。
3. **页面数据合法性**：校验页面展示的价格均为合法正数、指标字段类型正确，
   避免脏数据 / NaN / 空值流入展示层。

> 💡 `scripts/validate-data.sh` 可在执行测试前对 `test-data/*.json` 做**前置数据校验**，
> 确保测试数据本身合法完整，避免因测试数据错误导致误判。

## 真实 alva.ai 页面结构（按真实 DOM 对齐）

> 本框架的 page object 与选择器**已按 alva.ai 真实页面重写**，不再假设臆想的
> `/signup`、`/dashboard`、`/automation`、`/alerts`、`/market/data` 等路由。

真实 alva.ai 是一个**聊天式 AI 投资助手**，核心闭环如下：

| 真实路由 | 页面 | 关键选择器 | 页面对象 |
| --- | --- | --- | --- |
| `/new_chat` | 对话页（核心入口） | `[data-testid="homepage-hero-input"]` 内 `textarea`、`.homepage-template-chip`（skill 芯片） | `chat.page.ts` |
| `/login` | 登录页 | `[data-testid="login-popup-{google\|twitter\|telegram\|discord}"]`、`input[placeholder="Login with Email"]` | `login.page.ts` |
| `/portfolio` | 投资组合页 | `Connect your first account`、`Add`、`Settings` | `portfolio.page.ts` |
| `/explore` | 探索页 | `a[href*="/playbooks/"]` 卡片 | `explore.page.ts` |

关键事实（探索自 https://alva.ai/）：

- **无独立 Automation / Alert 表单页**。"自动化监控"（Live Playbook）与"价格/指标告警"
  都是**通过 `/new_chat` 的对话式 skill 发起**的——例如点击
  `Trade Setup Automation` / `Alpha Radar Setup` skill 芯片，或直接输入自然语言指令。
  因此 `automation.page.ts`、`alert.page.ts` 已对齐到真实对话式入口，而非假表单。
- **账号体系走社交/邮箱登录**，无独立注册页。访问受保护路由（如 `/settings`）会
  302 重定向到 `/login?returnTo=...`。
- 侧边栏登录入口为 `[data-testid="sidebar-login"]`；
  登录后侧边栏才会出现 Chat / Tasks / Alerts / Memory / Files 标签。

## 目录结构

```
alva-qa-automation/
├── README.md                      # 三个必答问题
├── package.json                   # 依赖管理
├── tsconfig.json                  # TypeScript 配置
├── playwright.config.ts           # Playwright 配置
├── run.sh                         # 主运行脚本（安装 + 执行 + 报告）
├── scripts/
│   ├── setup.sh                   # 环境安装脚本
│   ├── run-tests.sh               # 测试执行脚本
│   ├── generate-report.sh         # 报告生成脚本
│   └── validate-data.sh           # 金融数据校验脚本
├── tests/
│   ├── 01-onboarding.spec.ts      # 注册/登录测试
│   ├── 02-create-automation.spec.ts # 创建 Automation 测试（核心）
│   ├── 03-data-validation.spec.ts # 金融数据校验测试
│   ├── 04-alert-setup.spec.ts     # Alert 配置测试
│   └── fixtures.ts                # 共享测试夹具
├── pages/
│   ├── chat.page.ts               # 对话页面对象（/new_chat，核心入口）
│   ├── login.page.ts              # 登录页面对象（/login）
│   ├── portfolio.page.ts          # 投资组合页面对象（/portfolio）
│   ├── explore.page.ts            # 探索页面对象（/explore）
│   ├── automation.page.ts         # Automation 页面对象（对话式 skill 发起）
│   └── alert.page.ts              # Alert 页面对象（对话式 skill 发起）
├── utils/
│   ├── financial-data.ts          # 金融数据校验工具
│   ├── yahoo-finance.ts           # Yahoo Finance 数据获取
│   ├── ai-helper.ts               # AI 辅助断言
│   └── logger.ts                  # 日志工具
├── test-data/
│   ├── tickers.json               # 测试用 ticker 列表
│   └── expected-values.json       # 预期金融数据
├── reports/                       # 测试报告输出目录（截图/日志/trace 保留在此）
│   ├── html/
│   ├── json/
│   ├── logs/
│   └── screenshots/
└── .github/
    └── workflows/
        └── test.yml               # CI 配置
```

## 环境变量

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `ALVA_BASE_URL` | 被测平台地址 | `https://alva.ai/` |
| `CI` | CI 模式（更多重试、禁止 `.only`） | 由环境决定 |
| `ALVA_LOG_LEVEL` | 日志级别 | `debug`（本地）/ `info`（CI） |
| `RUN_NETWORK_TESTS` | 开启 Yahoo Finance 网络测试 | 关闭 |
| `AI_ENDPOINT` / `AI_API_KEY` | 接入真实 AI 断言服务 | 可选 |

## 示例：如何新增一个测试模块

1. 在 `pages/` 新增页面对象，封装目标页面的关键操作。
2. 在 `tests/` 新增 `NN-xxx.spec.ts`，按业务场景编写测试用例。
3. 如需校验金融数据，在 `utils/financial-data.ts` 扩展校验函数。
4. 运行 `./run.sh test -f NN-xxx.spec.ts` 验证。
