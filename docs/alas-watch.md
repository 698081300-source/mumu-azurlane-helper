# Alas 上游观察（自动）

每天一次；大节点期间每 2 小时一次。

## 2026-10-30 13:35（北京时间）

上游没新提交：672aeed（2026-10-29）

## 2026-10-29 13:36（北京时间）

上游：02f8265 → **672aeed**（2026-10-29）Merge pull request #6091 from LmeSzinc/bug_fix

**这次动了什么**（5 个提交）

- `Upd: Island Transport templates`
- `Fix: island collect should wait dock loading`
- `Revert "Tmp: Skip minigame before game client patches"`
- `Add: swipe for detecting supply pack not in the first page`
- `Merge pull request #6091 from LmeSzinc/bug_fix`
- 大世界·岛屿（与我们无关）：module/island_handler/dock.py
- 测试（与我们无关）：tests/island/transport/test_transport_list_screenshots.py
- 其它：assets/island/transport/Saltwater_Fish_Meat_2.png、module/freebies/supply_pack.py、module/island/collect.py…

**跟我们有关吗**：无关（改的是别的东西）

## 2026-10-28 09:12（北京时间）

上游没新提交：02f8265（2026-10-27）

## 2026-10-27 09:25（北京时间）

上游：fe83021 → **02f8265**（2026-10-27）Merge pull request #6086 from LmeSzinc/bug_fix

**这次动了什么**（8 个提交）

- `Opt: use milp as backend for production_plan_calculator`
- `Refactor: island production planner to be reused for island transport`
- `Add: [CN, JP] island transport`
- `Add: [EN] island transport`
- `Fix: always handle info bar after shop_refresh`
- 配置字段（我们写的 7 个值）：module/config/argument/args.json、module/config/argument/menu.json、module/config/argument/override.yaml…
- 大世界·岛屿（与我们无关）：module/island_handler/highs.py、module/island_handler/milp.py、module/island_handler/production_plan_calculator.py…
- 测试（与我们无关）：tests/island/transport/test_transport_list_screenshots.py、tests/island/transport/test_transport_policy.py、tests/island/transport/test_transport_refresh.py…
- 其它：alas.py、assets/cn/island/ISLAND_TRANSPORT_CLAIM.png、assets/cn/island/ISLAND_TRANSPORT_DETAIL_CLOSE.BUTTON.png…

**跟我们有关吗**：⚠️ 有关，建议看一眼

## 2026-10-26 08:09（北京时间）

上游：b7bcb1b → **fe83021**（2026-10-25）Merge pull request #6082 from LmeSzinc/bug_fix

**这次动了什么**（3 个提交）

- `Revert "Upd: Sync STRATEGY_OPENED to all servers (#6074)"`
- `Upd: Sync STRATEGY_OPENED.BUTTON to all servers (#6074)`
- `Merge pull request #6082 from LmeSzinc/bug_fix`
- 主界面/任务调度：module/handler/assets.py
- 其它：assets/en/handler/STRATEGY_OPENED.BUTTON.png、assets/jp/handler/STRATEGY_OPENED.BUTTON.png、assets/tw/handler/STRATEGY_OPENED.BUTTON.png

**跟我们有关吗**：⚠️ 有关，建议看一眼

## 2026-10-25 08:15（北京时间）

上游：4d88c22 → **b7bcb1b**（2026-10-25）Merge pull request #6081 from LmeSzinc/bug_fix

**这次动了什么**（9 个提交）

- `Test: add offline screenshot infrastructure`
- `Test: rewrite island coverage around screenshot goldens`
- `Fix: recover truncated island emotion limits`
- `Fix: recognize historical island restaurant products`
- `Fix: restore English island task name spacing`
- 主界面/任务调度：module/handler/assets.py
- 大世界·岛屿（与我们无关）：module/island_handler/dock_scanner.py、module/island_handler/restaurant.py
- 测试（与我们无关）：tests/island/test_business.py、tests/island/test_collect.py、tests/island/test_freebie.py…
- 其它：.gitignore、assets/en/handler/STRATEGY_OPENED.BUTTON.png、assets/island/character/Taihou.png…

**跟我们有关吗**：⚠️ 有关，建议看一眼

## 2026-10-24 08:32（北京时间）

上游没新提交：4d88c22（2026-10-23）

## 2026-10-23 12:36（北京时间）

上游：2fc8c1c → **4d88c22**（2026-10-23）Merge pull request #6072 from LmeSzinc/bug_fix

**这次动了什么**（19 个提交）

- `Add: War Archives Sleeping Sea and Islas de Libertad`
- `Chore: Remove outdated comment`
- `Fix: prioritize hard floor island productions`
- `Fix: amortize ranch second product over 3 batches`
- `Fix: export idle conversions as their source item`
- 关卡数据（新活动/新图）：campaign/Readme.md、campaign/event_20261022_cn/campaign_base.py、campaign/event_20261022_cn/sp.py…
- 关卡流程（三星判定相关）：module/campaign/run.py
- 配置字段（我们写的 7 个值）：module/config/argument/args.json、module/config/i18n/en-US.json、module/config/i18n/ja-JP.json…
- 大世界·岛屿（与我们无关）：module/island_handler/exchange.py、module/island_handler/production_plan_calculator.py、module/island_handler/recipe.py…
- 测试（与我们无关）：tests/island_handler/test_exchange.py、tests/island_handler/test_production_plan_calculator.py、tests/island_handler/test_recipe_fish.py…
- 其它：assets/cn/template/TEMPLATE_SIREN_TempestaGhostBoss02.gif、assets/cn/war_archives/TEMPLATE_TEMPESTA_AND_ISLAS_DE_LIBERTAD.png、assets/cn/war_archives/TEMPLATE_TEMPESTA_AND_THE_SLEEPING_SEA.png…

**新活动**
- event_20261022_cn：✅ 关卡文件已就绪

→ **可以写进线上表 `events` 了**：{"events": [{"id": "event_20261022_cn", "name": "10 月活动"}]}

**跟我们有关吗**：⚠️ 有关，建议看一眼

## 2026-10-22 22:54（北京时间）

上游没新提交：2fc8c1c（2026-10-20）

## 2026-10-22 14:53

上游没新提交：2fc8c1c（2026-10-19）

## 2026-10-22 14:52

上游没新提交：2fc8c1c（2026-10-19）
