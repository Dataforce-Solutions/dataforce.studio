# Мониторинг: пробелы против спеки

Аудит от 23.08 — сверка реализации с `spec_full.md` (Live Monitoring Unified Architecture
Spec). Здесь только то, чего **нет** или что расходится со спекой. Что уже сделано и где
были поломки — в `MONITORING_FIXES.md`.

Состояние на момент аудита: ветка `feat/monitoring-frontend`, 345 тестов сателлита и
137 тестов дашборда зелёные.

---

## Сначала главное: мок-данных нет

Отдельно фиксирую, потому что вопрос задавали: дашборд не показывает заглушек. Цепочка
живая целиком — инструментация в пути инференса
(`agent/handlers/model_server_handler.py:221` → `agent/monitoring/instrumentation.py`),
экспорт по OTLP в коллектор, хранение в GreptimeDB, расчёт в воркере
(`agent/monitoring/worker.py`), чтение живым SQL по HTTP
(`agent/monitoring/greptime_query.py`). Reference-профиль собирается SDK из настоящих
обучающих данных и лежит в артефакте. `grep` по `mock|fake|synthetic|stub` в
`agent/monitoring/` даёт только тестовые фикстуры и `_synthetic_span` — отрисовку события
одним спаном, когда коллектор трейс не отдал.

Единственная оговорка: на демо-стенде **трафик** синтетический (генераторы в проекте
`dfs_test`), но инференс и всё посчитанное поверх него — настоящие.

---

## 1. Realized performance и таргеты — нет совсем

**Спека**: Target Submission Flow, Realized Performance, Performance tab, пятая группа
алертов, `target_events` в Local Storage Model, «recompute affected performance windows
after delayed targets arrive».

**Факт**: `grep` по `target_event`, `target_coverage`, `realized`, `request_id` не находит
ничего — ни в `satellite/`, ни в `backend/`, ни во `frontend/src`.

Чего не хватает:

- **эндпоинт приёма таргетов** на сателлите (спека: «target submission directly to the
  Satellite Monitoring API», не через платформу);
- **`request_id`**: спека требует принимать его от клиента, сохранять и возвращать в
  ответе, чтобы по нему пришёл отложенный таргет. Сейчас возвращается только `X-Event-Id`
  (`agent/agent_api.py:168`), а `event_id` по спеке — локальный идентификатор строки
  хранилища, для джойна он не предназначен. **Это блокер: без `request_id` таргет некуда
  прикладывать, поэтому делать его надо первым.**
- **таблица `target_events`** и джойн с событием инференса по id — таргет приходит через
  часы или дни, ждать его в момент запроса нельзя;
- **метрики по типу задачи**: регрессия — MAE, RMSE, R², распределение остатков,
  predicted vs actual; бинарная — accuracy, precision, recall, F1, ROC-AUC, confusion
  matrix; многоклассовая — accuracy, macro/micro F1, log loss, confusion matrix;
  форкастинг — MAE/RMSE/MAPE по горизонтам. Плюс **target coverage** — доля предсказаний,
  получивших ответ;
- **пересчёт окон**: опоздавший таргет меняет уже посчитанное окно; механика догона окон в
  воркере есть (`worker.py::_pending_windows`), её надо переиспользовать;
- **вкладка Performance** с честным пустым состоянием — спека прямо требует, чтобы она
  говорила, что остальные разделы работают и без таргетов;
- **пятая группа алертов** — по деградации качества;
- **target availability status в шапке** дашборда.

Решение, принятое 20.08: реального потребителя таргетов пока нет, поэтому делаем
**API + демо-генератор** в `dfs_test` рядом с генераторами трафика, чтобы прогнать путь
целиком.

Оценка: несколько дней. Самый крупный незакрытый раздел спеки.

---

## 2. Output drift считается, но нигде не показан

**Спека**: вкладка Output Drift (пункт 8 структуры дашборда) плюс «output drift summary» в
содержимом Overview.

**Факт**: метрика работает — `agent/monitoring/output_drift.py` считает PSI по предсказаниям
и тренд `mean / median / p05 / p95` для регрессии, PSI по долям классов для классификации;
алерты группы `output_drift` поднимаются и видны на вкладке Alerts. Но:

- в Query API нет секции output drift (`agent/monitoring/api.py` — эндпоинта нет);
- в `OverviewResponse` (`agent/schemas/monitoring_query.py:119`) нет поля под сводку;
- в `DASHBOARD_TABS` (`monitoring-ui/src/composables/useMonitoringDashboard.ts:30`) нет
  вкладки.

Данные уже лежат в `monitoring_results`, нужен только путь наружу: эндпоинт + блок в UI.
В дизайне это `y_pred` median с полосой p05–p95.

Оценка: день. Самый дешёвый пункт списка.

---

## 3. Вкладка Runtime — ✅ закрыто 24.08

**Спека**: вкладка Runtime (пункт 5 структуры дашборда) — request count, success rate,
error rate, latency p50/p95, timeout count, разбивка по статусам, список runtime-алертов.

**Было**: `GET /monitoring/api/runtime` реализован, но UI его не вызывал ни разу — вкладки
не было, а Overview показывал три метрики из девяти (requests, error rate, latency p95).
Практическое следствие: алерт по таймаутам мог загореться, а подтвердить его числом было
негде.

**Стало**: вкладка `Runtime` между Overview и Traces
(`monitoring-ui/src/components/runtime/RuntimeTab.vue`), загрузка ленивая, как у остальных.
Показывает восемь карточек роллапа (requests, success rate, error rate, latency p50 / p95 /
max, timeouts, failed inferences), те же три графика, что и Overview, таблицу
**Outcome breakdown** и список runtime-алертов с переходом в тот же сайдбар.

Заодно достроен бэкенд — двух вещей из спеки в контракте не было:

- `success_rate` считается на сервере, а не выводится в UI из `error_rate`: дашборд метрик
  не считает. Пустое окно даёт 0%, а не 100% — никто не позвал, и читать это как идеальное
  окно неправильно;
- `status_breakdown` — новая модель `StatusBreakdownRow` (outcome, HTTP-код, count, share),
  группировка по паре «исход + код». Это то, что отличает перегруженный model server (504)
  от клиента с битым payload (422) при одинаковом error rate.

Плюс мелочи: runtime-алерты теперь запрашиваются с `dims`, поэтому в сайдбаре у них есть
история метрики и происхождение порога — как на остальных вкладках; карточка Timeouts
подсвечивается, как только счётчик ненулевой; окно без единого вызова показывает пустое
состояние, а не восемь нулей и три плоских графика; мета графиков вынесена в
`monitoring-ui/src/lib/charts.ts` и переиспользуется Overview.

Тесты: 347 на сателлите (+2), 145 на дашборде (+8). Бандл в `agent/monitoring/static`
пересобран.

---

## 4. Адаптеры типов задач покрыты частично

**Спека**: V1 поддерживает регрессию, бинарную и многоклассовую классификацию, форкастинг —
каждый со своими метриками output drift.

**Факт** (`agent/monitoring/output_drift.py`):

| Тип задачи | Спека требует | Есть |
| --- | --- | --- |
| Регрессия | PSI, mean, median, p05, p95, доли low/high | всё |
| Бинарная классификация | positive class rate, PSI вероятностей, распределение уверенности, threshold crossing rates | только PSI по долям классов |
| Многоклассовая | распределение классов, per-class probability summaries, распределение уверенности, top changed classes | только PSI по долям классов |
| Форкастинг | PSI/сдвиг по горизонтам, mean/median по горизонтам, ширина интервала | нет вообще |

Data quality и feature drift от типа задачи не зависят и работают для всех.

Делать по мере появления таких деплоев — сейчас на стенде регрессия и классификация.

---

## 5. Global controls — три из шести

**Спека** (Dashboard Header And Controls): time range, window granularity, compare against
reference or previous, severity filter, feature filter, manual or auto-refresh.

**Факт** (`monitoring-ui/src/components/GlobalControls.vue`): window (24h / 7d / 30d),
compare (reference / previous), severity (all / warning / critical), кнопка Refresh.

Не хватает:

- **granularity**: параметр в API есть и работает (`query.py:180`, `query.py:208`), UI
  всегда шлёт `auto`. Авто-зум серий частично закрывает потребность, но выбрать шаг руками
  нельзя;
- **feature filter как глобальный контрол**: измерение `feature` в API есть, но фича
  выбирается внутри вкладок Data quality и Feature drift, а не в шапке;
- **auto-refresh**: только ручная кнопка;
- **`compare=previous` работает не везде**: влияет только на дельты карточек Overview
  (`query.py:794 _previous_rollup`). На вкладках дрейфа сравнение всегда с reference.

---

## 6. Шапка: два поля пустые

**Спека** требует в шапке: имя, статус, артефакт, тип задачи, orbit/environment, последнее
посчитанное окно, статус reference-профиля, доступность таргетов.

Заполнено всё, кроме:

- **`environment`** — такого поля нет в записи деплоя на платформе (есть `orbit_id` без
  имени), UI его просто пропускает. Чтобы заполнить, платформа должна отдавать имя орбиты в
  `/satellites/v1/deployments`;
- **target availability status** — следствие пункта 1.

---

## 7. Мелкие расхождения

- **Overview: alert timeline.** Спека называет «alert timeline», реализован список баннеров
  с переходом в тот же сайдбар, что и на вкладке Alerts. По сути равноценно, но это
  расхождение с текстом спеки — стоит либо сделать таймлайн, либо зафиксировать замену.
- **Service lifecycle.** Спека описывает реконсиляцию сервисов мониторинга по наличию хотя
  бы одного `full`-деплоя. Фактически стек поднят всегда через `docker-compose.yml` и флаг
  `MONITORING_ENABLED`. Спека это для MVP разрешает явно («acceptable to ship the monitoring
  services as part of the Satellite installation and leave them idle»), и главное
  требование выполняется: для деплоя в `off` сырой IO не пишется
  (`model_server_handler.py:221` — гейт по `monitoring_enabled`).
- **Передеплоить старые модели.** Артефакты, собранные до правок SDK, не содержат
  `reference_projection` — облако reference на PCA-скаттере у них пустое. Проверено 19.08:
  пустые `019ffc8e`, `019ffc8f`, `01a0143d-4711`, `01a0143d-875b`.
- **Демо-стенд.** Три деплоя называются `01a014f8 monitored` / `01a01502 monitored` (PATCH
  имени отвечал 500), висит failed-деплой `01a014fd-1e82-7018-aaeb-f3485744b8bc`.
- **dev-группа `wasm/packages/dfs_webworker`**: тесты пакета не запускаются локально —
  `__init__.py` тянет forecasting → `statsmodels`, дальше `promptopt` → `httpx` → `optuna`,
  а в dev-зависимостях их нет.

---

## 8. Open Questions спеки

Спека заканчивается шестью открытыми вопросами. Пять из них закрыты де-факто, но нигде не
записаны — фиксирую здесь:

| # | Вопрос | Как решено |
| --- | --- | --- |
| 1 | Как сателлит отдаёт браузеру доступный URL: домен, VPN, локальная сеть, туннель | **не решён**; сейчас `MONITORING_FRAME_ANCESTORS` + `base_url` проставляются руками |
| 2 | Валидировать launch-token подписью локально или через introspection платформы | introspection: `POST` на платформу, `MonitoringHandler.introspect_token` |
| 3 | Сколько хранить сырой IO в GreptimeDB | TTL 30 дней на события, результаты и алерты (`MONITORING_*_TTL`) |
| 4 | Одна база на сателлит, неймспейс на деплой или другое разбиение | одна база `public`, разделение по колонке `deployment_id` |
| 5 | Какие окна материализовать сразу, какие считать по запросу | runtime и traces — по запросу из событий; data quality, дрейф, multivariate — материализуются воркером |
| 6 | Пороги PSI фиксированные или настраиваемые с самого начала | настраиваемые: правило из reference-профиля перекрывает дефолт метрики (`agent/monitoring/thresholds.py`) |

---

## Сверх спеки

Чтобы картина была честной в обе стороны — сделано то, чего спека для первого релиза не
требовала:

- **multivariate drift (PCA + махаланобис)** — спека выносила «advanced multivariate drift»
  за рамки первого релиза, метрика реализована и работает;
- **вкладка Traces** — спека выносила трейсы из платформенного дашборда, но на сателлите их
  не требовала; вкладка есть, с деревом спанов и разбором payload;
- **self-health воркера** — счётчики, `GET /monitoring/api/worker`, полоска на Overview и
  история падений метрик в `monitoring_worker_failures`.

---

## Порядок работ

1. ~~**Runtime tab**~~ — сделано 24.08, см. пункт 3.
2. **Output drift view** (~день) — данные есть, нужен эндпоинт и блок в UI.
3. **`request_id` в пути инференса** — блокер для таргетов, делать до всего остального в
   пункте 1 списка выше.
4. **Realized performance целиком** (несколько дней) — приём таргетов, хранение, метрики,
   пересчёт окон, вкладка, алерты.
5. **Адаптеры классификации и форкастинга** — по мере появления деплоев.
6. **Мелочи**: granularity в контролах, `environment` (требует правки платформы),
   auto-refresh, передеплой старых моделей, уборка на стенде.
