# Surge Adblock Hub

自动化索引、体检分析、融合去重并修复双上游 Loon 去广告插件，输出可直接订阅的 **Surge 模块（`.sgmodule`）**。

- **插件上游 1**：[LoonLab (103516)](https://loonlab.103516.xyz/Plugin/)（`sooyaaabo/LoonLab`）
- **插件上游 2**：[可莉插件中心 (Kelee)](https://hub.kelee.one)（`luestr/ProxyResource`）
- **转换规范参考与版本追踪**：[Script-Hub](https://github.com/Script-Hub-Org/Script-Hub)（[在线版](https://scripthub.vercel.app)）
- **自动更新**：GitHub Actions 每 **12 小时** 自动检查三方上游（北京时间 10:00 / 22:00），仅在内容有变化时自动提交更新。

---

## 直接订阅链接（Surge 模块）

### 8 合 1 汇总模块（推荐）
```text
https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/all-in-one.sgmodule
```

### 单 App 模块
| App | Surge 模块直链 |
|---|---|
| 淘宝 | `https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/taobao.sgmodule` |
| 京东 | `https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/jd.sgmodule` |
| 滴滴 | `https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/didi.sgmodule` |
| 高德地图 | `https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/amap.sgmodule` |
| 百度地图 | `https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/baidumap.sgmodule` |
| 小红书 | `https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/rednote.sgmodule` |
| 顺丰 | `https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/sf.sgmodule` |
| 小宇宙 | `https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/cosmos.sgmodule` |

---

## 相比直接转换，本项目自动修复了哪些坑？

1. **修复多数组索引 `delpaths` 拆分错位**：将 Loon `response.json.delete(["Result.cards[1]", "Result.cards[4]", ...])` 编译为单条原子 `delpaths(...)`，避免拆成多条顺序执行导致后续索引偏移删错卡片（如百度地图周边）。
2. **修复脚本名含方括号 `[xxx]` 报错**：自动清洗 `[高德地图]`、`[京东]`、`[小红书]` 等前缀，避免 Surge 合并校验报 `配置段标题应使用 [段名称] 格式`。
3. **修复同名脚本静默覆盖**：对同一模块和 8 合 1 汇总内的同名脚本自动追加 `_2` / `_3` 编号（如淘宝可莉版、高德、小红书均存在上游同名冲突）。
4. **自动补全漏配的 MITM 域名**：扫描最终生效的 Rewrite / Script 域名，自动补入未覆盖的 `hostname`（如百度地图漏配的 `maphotel.baidu.com`）。
5. **兼容 Script-Hub 核心特性**：支持 Query 参数无序匹配展开 `\?(?:[^#?&]+&)*`，支持 Loon `[Argument]` 开关转换为 Surge `#!arguments` 与 `{{{var}}}` 模板开关，并自动内联外部 `.jq` 文件（`jq_file`）。
6. **自动 `jq` 语法校验**：每次构建自动用 `jq` 校验全部 `http-response-jq` 表达式，确保 0 语法错误。

详细对比与体检结果见自动生成的 [ANALYSIS.md](./ANALYSIS.md)。

---

## 扩展更多 App

只需编辑 [`config/apps.json`](./config/apps.json) 添加新的双上游映射，推送后或手动触发 Actions 即可自动生成模块与分析报告。
