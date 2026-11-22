# 上游双源去广告分析与自动修复报告

> 本报告由 `scripts/sync_and_build.py` 自动生成。插件上游最新日期：**2026-11-02 21:00**
> 转换规范参考：[`Script-Hub-Org/Script-Hub`](https://github.com/Script-Hub-Org/Script-Hub)（最新提交 `863858b492` · 2026-11-20 · fix(stable): deduplicate Stash category metadata）

## 1. 总览对比表

| App | 103516 日期 / 规则数 | 可莉 日期 / 规则数 | 最终输出（Rule / Body / MapLocal / Script / MITM） | 单模块订阅 |
|---|---|---|---|---|
| **淘宝** (`taobao`) | 2026-11-02 (R:7 W:4 S:0) | 2026-10-02 (R:6 W:11 S:2) | 7 / 0 / 4 / 2 / 5 | [`taobao.sgmodule`](https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/taobao.sgmodule) |
| **京东** (`jd`) | 2026-11-02 (R:1 W:7 S:7) | 2026-10-02 (R:1 W:2 S:1) | 1 / 3 / 5 / 6 / 4 | [`jd.sgmodule`](https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/jd.sgmodule) |
| **滴滴** (`didi`) | 2026-11-02 (R:43 W:48 S:0) | 2026-10-02 (R:3 W:27 S:0) | 43 / 37 / 20 / 0 / 23 | [`didi.sgmodule`](https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/didi.sgmodule) |
| **高德地图** (`amap`) | 2026-11-02 (R:4 W:26 S:13) | 2026-10-20 (R:0 W:23 S:0) | 4 / 14 / 19 / 13 / 7 | [`amap.sgmodule`](https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/amap.sgmodule) |
| **百度地图** (`baidumap`) | 2026-11-02 (R:0 W:9 S:0) | 2026-10-02 (R:0 W:12 S:0) | 0 / 9 / 12 / 0 / 8 | [`baidumap.sgmodule`](https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/baidumap.sgmodule) |
| **小红书** (`rednote`) | 2026-11-02 (R:6 W:9 S:13) | 2026-10-02 (R:1 W:9 S:12) | 7 / 8 / 10 / 13 / 10 | [`rednote.sgmodule`](https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/rednote.sgmodule) |
| **顺丰** (`sf`) | 2026-11-02 (R:0 W:8 S:0) | 2026-10-02 (R:0 W:4 S:0) | 0 / 1 / 7 / 0 / 4 | [`sf.sgmodule`](https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/sf.sgmodule) |
| **小宇宙** (`cosmos`) | 2026-11-02 (R:0 W:7 S:0) | 2026-10-02 (R:0 W:5 S:0) | 0 / 3 / 5 / 0 / 1 | [`cosmos.sgmodule`](https://raw.githubusercontent.com/xfoxtbat/surge-adblock-hub/main/modules/cosmos.sgmodule) |

## 2. 逐 App 深度诊断与自动修复清单

### 淘宝 (`taobao`)
- **融合策略**：`103516_plus_kelee_scripts` — 保留 103516 的 AMDC 调度拦截与域名/图片规则，补入可莉的开屏与 poplayer 弹层脚本（拆名避免覆盖），排除易误杀首页的 newface.awesome.get。
- **103516 体检**：AMDC拦截=`True`，注释规则=`12` 条；无结构性异常
- **可莉 体检**：AMDC拦截=`False`，注释规则=`0` 条；发现问题：MITM 漏配域名：gw.alicdn.com；同名脚本冲突（Surge 后者覆盖前者）：移除淘宝开屏广告
- **已自动执行的修复与优化**：
  - 镜像外部脚本防 UA 拦截：`https://kelee.one/Resource/JavaScript/Taobao/Taobao_remove_ads.js` -> `scripts/vendor/kelee_Taobao_remove_ads.js` (3061B)
  - 自动消解同名脚本冲突：`移除淘宝开屏广告 -> 移除淘宝开屏广告_2`

### 京东 (`jd`)
- **融合策略**：`merge_103516_primary` — 以 103516 为主（保留比价等附加脚本），清洗方括号脚本名并去重融合可莉独有规则。
- **103516 体检**：AMDC拦截=`False`，注释规则=`1` 条；发现问题：脚本名含方括号 `[...]`（会导致 Surge 合并报段标题错误）
- **可莉 体检**：AMDC拦截=`False`，注释规则=`0` 条；无结构性异常
- **已自动执行的修复与优化**：
  - 清洗方括号脚本名：`[京东]移除广告` -> `京东_移除广告`
  - 镜像外部脚本防 UA 拦截：`https://rucu6.pages.dev/Scripts/jingdong.js` -> `scripts/vendor/rucu6_jingdong.js` (9554B)
  - 清洗方括号脚本名：`[京东比价]获取慢慢买Cookie` -> `京东比价_获取慢慢买Cookie`
  - 镜像外部脚本防 UA 拦截：`https://raw.githubusercontent.com/mw418/Loon/main/script/jd_price.js` -> `scripts/vendor/mw418_jd_price.js` (28147B)
  - 清洗方括号脚本名：`[京东比价]标题嵌入版` -> `京东比价_标题嵌入版`
  - 清洗方括号脚本名：`[京东比价]详情通知版` -> `京东比价_详情通知版`
  - 清洗方括号脚本名：`[京东比价]详情嵌入版（表格图）` -> `京东比价_详情嵌入版（表格图）`
  - 清洗方括号脚本名：`[京东比价]详情嵌入版（折线图）` -> `京东比价_详情嵌入版（折线图）`
  - 镜像外部脚本防 UA 拦截：`https://loon.103516.xyz/Script/JingDong/JingDong.price.js` -> `scripts/vendor/103516_JingDong.price.js` (25021B)

### 滴滴 (`didi`)
- **融合策略**：`merge_103516_primary` — 以 103516 为主（覆盖更全），补充融合可莉未重复的规则，校验 MITM 域名完整性并剔除实测触发 SSL Certificate Pinning 的域名。
- **103516 体检**：AMDC拦截=`False`，注释规则=`16` 条；发现问题：MITM 漏配域名：htwkop-st.xiaojukeji.com, poi.map.xiaojukeji.com, travel-alioth.xiaojukeji.com
- **可莉 体检**：AMDC拦截=`False`，注释规则=`0` 条；无结构性异常
- **已自动执行的修复与优化**：
  - 自动补全漏配 MITM 域名：`travel-alioth.xiaojukeji.com`
  - 剔除实测触发 SSL Certificate Pinning 的 MITM 域名：`common.diditaxi.com.cn, poi.map.xiaojukeji.com`

### 高德地图 (`amap`)
- **融合策略**：`merge_103516_primary` — 以 103516 为主（含 AMDC 拦截与 rucu6 脚本），自动修复同名脚本冲突与方括号脚本名，并内联双方引用的外部 .jq 文件。
- **103516 体检**：AMDC拦截=`True`，注释规则=`16` 条；发现问题：同名脚本冲突（Surge 后者覆盖前者）：[高德地图]移除路线规划推广, [高德地图]移除首页推广；脚本名含方括号 `[...]`（会导致 Surge 合并报段标题错误）
- **可莉 体检**：AMDC拦截=`False`，注释规则=`0` 条；无结构性异常
- **已自动执行的修复与优化**：
  - 内联外部 jq_file: Amap.recommend.jq
  - 清洗方括号脚本名：`[高德地图]移除路线规划推广` -> `高德地图_移除路线规划推广`
  - 镜像外部脚本防 UA 拦截：`https://rucu6.pages.dev/Scripts/amap.js` -> `scripts/vendor/rucu6_amap.js` (20651B)
  - 清洗方括号脚本名：`[高德地图]移除路线规划、导航结束页推广` -> `高德地图_移除路线规划、导航结束页推广`
  - 清洗方括号脚本名：`[高德地图]移除导航详情页底部酒店、处理附近页` -> `高德地图_移除导航详情页底部酒店、处理附近页`
  - 清洗方括号脚本名：`[高德地图]移除搜索栏推广` -> `高德地图_移除搜索栏推广`
  - 清洗方括号脚本名：`[高德地图]移除搜索详情页推广` -> `高德地图_移除搜索详情页推广`
  - 清洗方括号脚本名：`[高德地图]移除首页推广` -> `高德地图_移除首页推广`
  - 清洗方括号脚本名：`[高德地图]移除附近页推广` -> `高德地图_移除附近页推广`
  - 清洗方括号脚本名：`[高德地图]移除开屏广告` -> `高德地图_移除开屏广告`
  - 清洗方括号脚本名：`[高德地图]移除打车页推广卡片、弹窗` -> `高德地图_移除打车页推广卡片、弹窗`
  - 清洗方括号脚本名：`[高德地图]移除打车页红点角标、天气图标` -> `高德地图_移除打车页红点角标、天气图标`
  - 清洗方括号脚本名：`[高德地图]移除导航详情页推广` -> `高德地图_移除导航详情页推广`
  - 内联外部 jq_file: updatable.jq
  - 内联外部 jq_file: search_poi_detail.jq
  - 自动消解同名脚本冲突：`高德地图_移除路线规划推广 -> 高德地图_移除路线规划推广_2; 高德地图_移除首页推广 -> 高德地图_移除首页推广_2`

### 百度地图 (`baidumap`)
- **融合策略**：`merge_103516_primary` — 修复多数组索引 delpaths 拆分错位问题，自动补全漏掉的 maphotel.baidu.com MITM 域名。注意：可莉原版标注 App Store 版可能因 SSL Pinning 无法解密。
- **103516 体检**：AMDC拦截=`False`，注释规则=`1` 条；无结构性异常
- **可莉 体检**：AMDC拦截=`False`，注释规则=`0` 条；发现问题：MITM 漏配域名：maphotel.baidu.com；作者标注需 IPA 签名 / SSL Unpinning（App Store 版可能无法解密）；多数组索引 delpaths（常见转换器拆分后会导致索引错位）
- **已自动执行的修复与优化**：
  - 修复多数组索引删除为单条原子 delpaths
  - 自动补全漏配 MITM 域名：`maphotel.baidu.com`

### 小红书 (`rednote`)
- **融合策略**：`merge_103516_primary` — 以 103516 为主（保留去水印与时间显示脚本），自动修复同名信息流脚本冲突与方括号脚本名。
- **103516 体检**：AMDC拦截=`False`，注释规则=`3` 条；发现问题：同名脚本冲突（Surge 后者覆盖前者）：[小红书]移除信息流广告；脚本名含方括号 `[...]`（会导致 Surge 合并报段标题错误）
- **可莉 体检**：AMDC拦截=`False`，注释规则=`0` 条；发现问题：同名脚本冲突（Surge 后者覆盖前者）：移除信息流广告
- **已自动执行的修复与优化**：
  - 清洗方括号脚本名：`[小红书]移除整体配置 ui` -> `小红书_移除整体配置_ui`
  - 镜像外部脚本防 UA 拦截：`https://rucu6.pages.dev/Scripts/xiaohongshu.js` -> `scripts/vendor/rucu6_xiaohongshu.js` (20194B)
  - 清洗方括号脚本名：`[小红书]移除开屏广告 config` -> `小红书_移除开屏广告_config`
  - 清洗方括号脚本名：`[小红书]移除开屏广告 splash_config` -> `小红书_移除开屏广告_splash_config`
  - 清洗方括号脚本名：`[小红书]移除详情页小部件、关注页感兴趣的人` -> `小红书_移除详情页小部件、关注页感兴趣的人`
  - 清洗方括号脚本名：`[小红书]移除详情页感兴趣的人` -> `小红书_移除详情页感兴趣的人`
  - 清洗方括号脚本名：`[小红书]首页笔记标题前显示时间` -> `小红书_首页笔记标题前显示时间`
  - 镜像外部脚本防 UA 拦截：`https://loon.103516.xyz/Script/RedNote/RedNote.feedtime.js` -> `scripts/vendor/103516_RedNote.feedtime.js` (1558B)
  - 清洗方括号脚本名：`[小红书]移除信息流广告` -> `小红书_移除信息流广告`
  - 清洗方括号脚本名：`[小红书]移除搜索页广告` -> `小红书_移除搜索页广告`
  - 清洗方括号脚本名：`[小红书]移除图片和实况照片水印` -> `小红书_移除图片和实况照片水印`
  - 清洗方括号脚本名：`[小红书]移除图片和视频水印` -> `小红书_移除图片和视频水印`
  - 清洗方括号脚本名：`[小红书]移除视频水印` -> `小红书_移除视频水印`
  - 清洗方括号脚本名：`[小红书]移除评论区实况照片水印` -> `小红书_移除评论区实况照片水印`
  - 镜像外部脚本防 UA 拦截：`https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/xiaohongshu/xiaohongshu.js` -> `scripts/vendor/fmz200_xiaohongshu.js` (27135B)
  - 自动消解同名脚本冲突：`小红书_移除信息流广告 -> 小红书_移除信息流广告_2`

### 顺丰 (`sf`)
- **融合策略**：`merge_103516_primary` — 以 103516 为主，融合可莉独有规则并统一转换 response.body.mock 为 Surge Map Local。
- **103516 体检**：AMDC拦截=`False`，注释规则=`0` 条；无结构性异常
- **可莉 体检**：AMDC拦截=`False`，注释规则=`0` 条；无结构性异常
- **已自动执行的修复与优化**：无额外冲突需修正。

### 小宇宙 (`cosmos`)
- **融合策略**：`merge_103516_primary` — 以 103516 为主，融合可莉独有重写规则并校验 MITM 域名。
- **103516 体检**：AMDC拦截=`False`，注释规则=`2` 条；无结构性异常
- **可莉 体检**：AMDC拦截=`False`，注释规则=`0` 条；无结构性异常
- **已自动执行的修复与优化**：无额外冲突需修正。

## 3. JQ 语法自检

- ✅ 全部 `http-response-jq` 表达式均通过 `jq` 编译校验。
