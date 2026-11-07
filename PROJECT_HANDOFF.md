# MLChess: текущее состояние, продуктовая идея и техническое направление

> Актуальность документа: 7 ноября 2026 года  
> Репозиторий: <https://github.com/Maielafon123/mlchess>  
> Назначение: исходный контекст для ChatGPT, технического архитектора и команды разработки.

## 1. Как использовать этот документ

Этот файл описывает:

- что уже реализовано и проверено;
- что существует только как идея или архитектурное решение;
- текущее устройство нейросети, данных, MCTS и self-play;
- целевую игровую и учебную платформу;
- подход к уровням Elo;
- требования к локальной работе;
- ближайшие этапы разработки и критерии готовности;
- известные риски и нерешённые вопросы.

При подготовке задания для команды нельзя считать будущие компоненты уже готовыми. Разделы
«Текущее состояние» и «Ограничения» являются фактическим состоянием проекта. Остальные разделы —
целевая архитектура и план.

---

## 2. Краткая идея проекта

MLChess должен стать локальной шахматной платформой, объединяющей:

1. Собственный обучаемый policy-value движок.
2. MCTS-поиск и self-play обучение.
3. Игру против соперников разной, измеренной силы.
4. Режим игры с тренером.
5. Просмотр лучшего хода и нескольких альтернатив.
6. Понятные объяснения критических решений.
7. Дебютную базу, типовые планы, тактику и окончания.
8. Персональный профиль ученика и задания из его ошибок.
9. Полностью локальную игру без обязательного облака.
10. Dashboard для наблюдения за обучением и self-play.

Главный продуктовый принцип:

> Сильный шахматный ход и полезное учебное объяснение — разные результаты. Движок отвечает за
> шахматные факты, а тренер выбирает, как и когда их показать ученику.

---

## 3. Текущее состояние проекта

### 3.1. Что уже работает

- Потоковое чтение обычных и Zstandard-сжатых PGN.
- Чтение больших датасетов без полной распаковки в RAM.
- Фильтрация Chess960 для первой версии standard chess.
- Каноническое представление позиции от лица стороны, которая ходит.
- AlphaZero-подобное пространство из 4672 действий.
- Encode/decode ходов, включая рокировку, en passant и превращения.
- Legal move mask.
- Residual policy/Q/WDL сеть на PyTorch.
- Supervised training с AMP/BF16 на CUDA.
- Source-balanced sampling из Lc0, ChessBench и puzzles.
- Checkpoints, resume, инициализация нового run от старого checkpoint.
- JSONL-метрики обучения и валидации.
- PUCT MCTS.
- Консольная игра человека против checkpoint.
- Генерация self-play партий.
- Компактный replay-формат `.npz` с MCTS visit counts.
- Смешивание supervised и self-play данных.
- Soft policy target по visit-count распределению MCTS.
- Локальный Flask-dashboard.
- Live-показ self-play доски, истории ходов и состояния партии.
- 19 автоматических тестов на момент последней проверки.

### 3.2. Что пока не реализовано

- Рейтинговая arena для честного сравнения checkpoint-ов.
- Статистическая оценка Elo.
- Автоматический model registry: `candidate`, `best`, `rejected`.
- Batched MCTS по нескольким партиям.
- Tree reuse и полноценный transposition cache.
- Масштабное self-play обучение на тысячах партий.
- Human move model по рейтинговым человеческим партиям.
- Уровни 800/1200/1600/2000 Elo.
- Структурированный Analysis API / MultiPV.
- Классификация ошибок и тактических мотивов.
- База дебютов, планов и окончаний.
- Student model и персонализация.
- Полноценный игровой web/desktop-интерфейс.
- Tauri-обёртка и установщик.
- Объясняющий тренер.
- Доказанный игровой рейтинг текущей модели.

### 3.3. Важное ограничение

Текущая сеть является доказательством работоспособности пайплайна, а не готовым сильным движком.
Нельзя оценивать её реальный Elo только по policy top-1, WDL accuracy или train loss.

---

## 4. Локальная среда и данные

### 4.1. Известное железо

- GPU: NVIDIA RTX 5060 Ti, 16 ГБ VRAM.
- CPU: Intel Core i5-12400F.
- RAM: примерно 32 ГБ.
- ОС: Windows.
- Python: 3.12.7 на момент первых прогонов.
- PyTorch: 2.10 CUDA 12.8 на момент первых прогонов.

### 4.2. Датасет

Используется `KeithG33/ChessBot-Dataset`.

- Локальный train: около 30,64 ГБ.
- Train shards: 1702 `.pgn.zst` файла.
- Заявленное количество train-позиций: примерно 3,368 млрд.
- Официальный test: 32 shard-а, около 157 МБ.
- Test-позиций: примерно 16,9 млн.

Распределение train shard-ов по текущему header-классификатору:

- Lc0: 1410 shard-ов.
- ChessBench: 275 shard-ов.
- Puzzles: 17 shard-ов.

Исходные PGN, checkpoints, `runs/`, Hugging Face cache и self-play artifacts не хранятся в GitHub.
Они исключены через `.gitignore`.

### 4.3. Текущая смесь supervised источников

- Lc0: 70%.
- ChessBench: 20%.
- Puzzles: 10%.

Это стартовая эвристика. В дальнейшем веса должны определяться source-wise метриками и задачами
конкретного training run.

---

## 5. Представление шахматной позиции

### 5.1. Input

Позиция кодируется как tensor `20 × 8 × 8`, всегда от лица стороны, которая ходит.

- Плоскости 0–5: свои pawn, knight, bishop, rook, queen, king.
- Плоскости 6–11: фигуры соперника.
- Плоскости 12–15: права на рокировку обеих сторон.
- Плоскость 16: en passant square.
- Плоскость 17: halfmove clock, нормализованный на 100.
- Плоскости 18–19: признаки повторения позиции.

Для чёрных координаты канонизируются вертикальным отражением. Одна сеть играет обоими цветами.

### 5.2. Action space

Используется `73 × 8 × 8 = 4672` logits:

- queen-like направления и расстояния;
- ходы коня;
- отдельные underpromotion действия.

Queen promotion кодируется обычным queen-like ходом. Нелегальные действия исключаются legal mask.

### 5.3. Инварианты

- Policy target всегда должен быть legal.
- Encode/decode хода должен давать round-trip.
- Value всегда интерпретируется от лица стороны, которая ходит.
- При переходе на следующий ply знак value меняется.
- Standard castling и Chess960 rook-square notation нормализуются.

---

## 6. Текущая нейросеть

### 6.1. Архитектура

Текущий основной вариант:

- Input: 20 каналов.
- Stem: convolution `3 × 3`.
- Residual trunk: 10 блоков.
- Width: 128.
- Примерно 2 999 245 обучаемых параметров.

Heads:

1. Policy: 4672 logits.
2. Q: scalar `tanh`, диапазон `[-1, 1]`.
3. WDL: logits классов win/draw/loss.

### 6.2. Loss

Текущая формула:

```text
L = L_policy + 0.5 * L_q + 0.2 * L_wdl
```

- Policy: legal-masked cross entropy.
- Для self-play policy target является мягким распределением MCTS visit counts.
- Q: Smooth L1 / Huber loss.
- WDL: cross entropy только для известных результатов.

### 6.3. Supervised pretrain v1

Конфигурация:

- ResNet 10×128.
- Batch size 256.
- 10 000 training steps.
- CUDA/BF16.
- 4096 test-примеров в каждой контрольной оценке.

Финальные метрики шага 10 000:

- Eval loss: `2.2911`.
- Policy top-1: `34.03%`.
- Q MAE: `0.1914`.
- WDL accuracy: `65.97%`.

Лучшее наблюдавшееся policy top-1 внутри pretrain было около `34.69%` на шаге 9000.

### 6.4. Self-play fine-tune v2

Данные:

- 4 self-play партии.
- 298 полуходов.
- 8 MCTS simulations на ход.

Fine-tune:

- 1000 шагов.
- 10% self-play, 90% supervised.
- Learning rate `2e-4`.
- Инициализация от `pretrain-v1`.

Лучший промежуточный checkpoint: шаг 750.

- Policy top-1: `34.42%`.
- Q MAE: `0.1928`.
- WDL accuracy: `68.02%`.

Финальный checkpoint шага 1000:

- Policy top-1: `34.67%`.
- Q MAE: `0.2024`.
- WDL accuracy: `66.85%`.

Checkpoint шага 750 выглядит лучше по совокупности Q/WDL, но это нельзя считать доказательством
его большей игровой силы без arena-матчей.

---

## 7. MCTS и self-play

### 7.1. Текущий MCTS

Используется PUCT:

```text
score = -Q_child + c_puct * P_child * sqrt(N_parent + 1) / (1 + N_child)
```

Node хранит:

- prior;
- visit count;
- value sum;
- children;
- соответствие action → move;
- board state.

Terminal-результат определяется правилами `python-chess`, включая claimable draw.

### 7.2. Текущие ограничения MCTS

- Один inference на leaf.
- Нет batching листьев разных партий.
- Нет tree reuse после сыгранного хода.
- Нет transposition table.
- Python остаётся потенциальным bottleneck.
- Self-play пока слишком мал для серьёзного reinforcement learning.

### 7.3. Replay format

Self-play партия сохраняется в `.npz` без object arrays:

- `states`;
- `turns`;
- `values`;
- `policy_offsets`;
- `policy_actions`;
- `policy_visits`;
- `moves`;
- `winner`.

Visit-count policy хранится sparse, а не как dense массив 4672 float на каждую позицию.

### 7.4. Целевой self-play цикл

1. `best` или `candidate` генерирует партии.
2. MCTS visit counts становятся policy target.
3. Итог партии становится value/WDL target.
4. Новые партии добавляются в ограниченный replay buffer.
5. Learner смешивает self-play и expert data.
6. Новый candidate проходит arena против best.
7. Candidate публикуется как best только после статистического подтверждения.

Ориентир будущего replay buffer: 1–5 млн последних позиций, а не бесконечное накопление всех игр.

---

## 8. Целевая игровая платформа

### 8.1. Основные пользовательские режимы

#### Рейтинговая игра

- Игра без подсказок во время партии.
- Выбор приблизительного уровня соперника.
- Часы и контроль времени.
- Локальный рейтинг пользователя.
- Послематчевый разбор.

#### Игра с тренером

- Подсказки по запросу.
- Короткие остановки в критические моменты.
- Вопросы перед раскрытием ответа.
- Возможность отмены хода в учебном режиме.
- После партии — основные ошибки и упражнения.

#### Анализ позиции

- Загрузка FEN или PGN.
- Лучший ход.
- Несколько альтернатив MultiPV.
- WDL и оценка позиции.
- Principal variation.
- Объяснение планов, угроз и тактических мотивов.

### 8.2. Предлагаемый локальный стек

Это направление, а не окончательно зафиксированный выбор:

- Desktop shell: Tauri.
- Frontend: React + TypeScript.
- Шахматная доска: специализированный React board component или собственный компонент.
- Local API: FastAPI/Python worker.
- Engine runtime: сначала PyTorch CUDA, затем ONNX Runtime/TensorRT при необходимости.
- Storage: SQLite + файлы моделей/replay.
- Независимый oracle: локальный Stockfish binary.

### 8.3. Почему local-first

- Работа без интернета.
- Нет обязательной оплаты серверного GPU.
- Партии и профиль ученика остаются у пользователя.
- Возможность использовать локальную видеокарту.
- Простое сохранение PGN, checkpoints и настроек.

### 8.4. Разделение процессов

- UI не должен напрямую импортировать PyTorch.
- UI общается со стабильным локальным API.
- Training runtime отделён от игрового runtime.
- Desktop-приложение использует опубликованный model bundle, а не произвольный training checkpoint.
- Обновление модели должно быть атомарным и обратимым.

---

## 9. Предлагаемые сервисы и модули

### 9.1. Game Service

Отвечает за:

- состояние партии;
- legal moves;
- clocks;
- draw/resign;
- PGN;
- undo в учебном режиме;
- сохранение и восстановление локальных партий.

### 9.2. Engine Service

Отвечает за:

- загрузку model bundle;
- raw policy/value inference;
- MCTS;
- MultiPV;
- best move;
- анализ с заданным time/node budget;
- уровни силы;
- performance telemetry.

### 9.3. Analysis Service

Преобразует движковые числа в структурированные шахматные факты:

- оценка сыгранного хода;
- centipawn/value loss;
- best/good/inaccuracy/mistake/blunder;
- угрозы;
- материал;
- безопасность короля;
- слабые поля и пешечные структуры;
- тактические мотивы;
- critical positions.

### 9.4. Coach Service

Решает:

- нужно ли вмешиваться сейчас;
- какой уровень подсказки показать;
- что ученик уже знает;
- какой вопрос задать;
- какое объяснение сформировать;
- какое упражнение создать из ошибки.

### 9.5. Knowledge Base

Хранит:

- ECO;
- названия дебютов;
- дерево/граф вариантов с транспозициями;
- типовые планы обеих сторон;
- пешечные структуры;
- тематические тактики;
- частые ошибки;
- базовые окончания;
- учебные тексты и ссылки на мотивы.

### 9.6. Student Model

Хранит:

- локальный игровой рейтинг;
- уровень дебюта, тактики, миттельшпиля и окончаний;
- темы, которые ученик знает или забывает;
- успешность без подсказки и с подсказками;
- частые ошибки;
- личный дебютный репертуар;
- очередь spaced repetition.

---

## 10. Контракт анализа

Нужен единый сериализуемый `AnalysisResult`, общий для UI, CLI, тестов и тренера.

Черновой пример:

```json
{
  "fen": "...",
  "side_to_move": "white",
  "budget": {
    "time_ms": 1000,
    "simulations": 256
  },
  "top_moves": [
    {
      "uci": "e2e4",
      "san": "e4",
      "prior": 0.24,
      "visits": 103,
      "q": 0.18,
      "wdl": [0.38, 0.44, 0.18],
      "pv": ["e2e4", "e7e5", "g1f3"]
    }
  ],
  "position_facts": {
    "material_balance": 0,
    "checks": [],
    "hanging_pieces": [],
    "king_safety": {}
  },
  "opening": {
    "eco": "C20",
    "name": "King's Pawn Game",
    "book_move": true
  },
  "confidence": {
    "engine_agreement": 0.86,
    "oracle_checked": false
  }
}
```

Точные поля должны быть оформлены отдельной JSON Schema/OpenAPI спецификацией.

---

## 11. Тренер и объяснения

### 11.1. Принцип grounding

LLM или шаблонный генератор не определяет лучший ход самостоятельно. Он получает факты из
`AnalysisResult`, дебютной базы и student model.

Любое объяснение должно быть проверяемо:

- названный ход legal;
- показанный вариант соответствует PV;
- WDL и оценка получены от движка;
- тактический мотив подтверждён feature detector или oracle;
- объяснение не противоречит позиции.

### 11.2. Лестница подсказок

1. **Наблюдение:** «Что изменил последний ход соперника?»
2. **Направление:** подсветить зону или проблемную фигуру.
3. **Идея:** назвать план или тактический мотив.
4. **Кандидаты:** показать 2–3 разумных хода без ответа.
5. **Решение:** лучший ход, оценка и короткая PV.

Приложение начинает с минимальной помощи и повышает уровень только после запроса или неудачной
попытки.

### 11.3. Что объяснять во время партии

Не следует показывать длинное объяснение после каждого очевидного хода. Рекомендуемый UX:

- короткое сообщение только в критических позициях;
- индикатор, что предыдущий ход заслуживает внимания;
- подробное объяснение по запросу;
- полный разбор после партии;
- 3–7 важнейших решений вместо стены текста.

### 11.4. Формат объяснения критического решения

1. Что изменилось в позиции.
2. Какая угроза появилась.
3. Какие кандидаты были разумны.
4. Какой принцип или мотив решает позицию.
5. Почему лучший ход превосходит альтернативы.
6. Короткий доказательный вариант.
7. Вопрос или упражнение на закрепление.

---

## 12. Уровни Elo

### 12.1. Главное правило

Нельзя присвоить движку «1600 Elo» только по количеству MCTS simulations или policy accuracy.
Каждый уровень должен быть измерен в arena и иметь диапазон неопределённости.

### 12.2. Предлагаемые пользовательские уровни

Первый продуктовый набор:

- Beginner: примерно 800–1000.
- Casual: примерно 1100–1300.
- Club: примерно 1400–1700.
- Strong club: примерно 1800–2000.
- Advanced: 2100+ при достаточной силе базового движка.

Конкретные числа нельзя обещать до калибровки.

### 12.3. Почему недостаточно уменьшить поиск

Маленький search budget:

- сильно зависит от типа позиции;
- иногда всё равно находит сильный очевидный ход;
- иногда пропускает грубую тактику случайным образом;
- не создаёт правдоподобный человеческий стиль;
- не контролирует частоту и тяжесть ошибок.

### 12.4. Предлагаемая Elo policy

Для каждого хода:

1. Сильный движок получает top-k кандидатов.
2. Профиль задаёт ожидаемый centipawn/value loss.
3. Кандидаты фильтруются по допустимой тяжести ошибки.
4. Human move model оценивает правдоподобность человеческого выбора.
5. Blunder governor контролирует частоту грубых ошибок.
6. Запрещаются карикатурные ошибки, например необоснованный пропуск мата в один ход.
7. Итоговая сила измеряется arena-матчами.

Параметры профиля могут включать:

- target Elo;
- search time / simulations;
- policy temperature;
- expected centipawn loss;
- blunder probability;
- максимальную тяжесть ошибки;
- opening book depth;
- endgame assistance;
- time-pressure behavior;
- preferred style.

### 12.5. Нужные дополнительные данные

Для human move model требуется корпус человеческих партий с:

- рейтингом игроков;
- контролем времени;
- желательно timestamp/clock information;
- результатом партии;
- фильтрацией читеров, ботов и аномальных партий.

Текущий Lc0/ChessBench/puzzle датасет не позволяет достоверно моделировать игрока конкретного Elo.

---

## 13. Arena и измерение силы

### 13.1. Почему arena является ближайшим приоритетом

Сейчас выбор checkpoint опирается на validation metrics. Это недостаточно для игровой силы.
Следующий обязательный компонент — arena runner.

### 13.2. Требования к arena v1

- Checkpoint A против checkpoint B.
- Одинаковые MCTS budgets.
- Фиксированный opening suite.
- Каждая стартовая позиция играется обоими цветами.
- Сохранение PGN.
- Win/draw/loss статистика.
- Score и confidence interval.
- Elo difference estimate.
- Reproducible seed/config.
- Возможность resume.
- Результаты отображаются в dashboard.

### 13.3. Размер выборки

Нельзя делать вывод по 2–20 партиям. Первый ориентир:

- минимум 200 игр для обычного сравнения;
- либо sequential probability ratio test;
- больше игр при высокой доле ничьих или близкой силе.

### 13.4. Соперники для калибровки

- Random legal mover.
- Простая material/greedy эвристика.
- Raw policy без MCTS.
- Предыдущие checkpoints.
- `best` model.
- Stockfish с фиксированными nodes/time/skill parameters.
- В дальнейшем — человеческие тестовые пулы.

### 13.5. Model registry

Предлагаемые состояния:

- `training`;
- `candidate`;
- `testing`;
- `best`;
- `rejected`;
- `archived`.

Model bundle должен включать:

- weights;
- model config;
- input encoding version;
- action mapping version;
- calibration profile;
- training metadata;
- git commit;
- arena results;
- API compatibility version.

---

## 14. Dashboard

Текущий dashboard реализован на Flask и работает локально по адресу:

```text
http://127.0.0.1:8501
```

Он уже показывает:

- список training runs;
- loss;
- policy top-1;
- WDL accuracy;
- Q MAE;
- checkpoints;
- количество self-play replay партий;
- live self-play доску;
- последний ход и историю партии.

Дальнейшее развитие dashboard:

- arena runs;
- Elo estimates и confidence intervals;
- candidate/best model registry;
- просмотр PGN;
- сравнение моделей;
- throughput/GPU telemetry;
- self-play outcome distribution;
- фильтры по источникам данных;
- кнопки безопасного запуска/остановки локальных jobs;
- уведомления об ошибках и завершении run.

Dashboard обучения и конечный пользовательский игровой UI должны оставаться разными приложениями
или как минимум разными режимами.

---

## 15. Предлагаемая дорожная карта

### Фаза 1. Arena v1

Результат:

- checkpoint-vs-checkpoint матчи;
- PGN;
- opening pairs;
- Elo difference;
- dashboard integration.

Критерий завершения:

- 200+ воспроизводимых игр;
- корректная смена цветов;
- resume;
- отсутствие illegal moves;
- статистический отчёт.

### Фаза 2. Оптимизация search

Результат:

- batched leaf inference;
- несколько параллельных партий;
- tree reuse;
- profiling;
- latency budgets.

Критерий завершения:

- GPU не простаивает большую часть времени;
- измеренный рост simulations/second;
- одинаковые результаты deterministic fixtures.

### Фаза 3. Main supervised training

Ориентир:

- 100–300 млн просмотренных позиций;
- source-wise validation;
- стабильные checkpoints;
- сравнение размеров модели после benchmark.

Критерий завершения:

- validation plateau;
- отсутствие source regressions;
- MCTS baseline показывает приемлемую силу в arena.

### Фаза 4. Масштабный self-play

Результат:

- actors;
- learner;
- replay window;
- тысячи партий на итерацию;
- автоматическая candidate promotion.

Критерий завершения:

- несколько последовательных итераций дают положительный Elo trend.

### Фаза 5. Elo calibration

Результат:

- фиксированные пользовательские профили;
- human move dataset;
- blunder governor;
- Stockfish/reference calibration.

Критерий завершения:

- каждый уровень имеет измеренный диапазон рейтинга;
- уровни монотонны;
- ошибки выглядят правдоподобно.

### Фаза 6. Analysis API

Результат:

- MultiPV;
- move grading;
- position facts;
- motifs;
- confidence;
- Stockfish cross-check.

Критерий завершения:

- единый контракт используется CLI, тестами и UI;
- эталонные позиции проходят regression suite.

### Фаза 7. Local game MVP

Результат:

- desktop/web UI;
- доска и часы;
- локальная партия;
- выбор соперника;
- лучший ход;
- PGN;
- сохранение истории.

Критерий завершения:

- пользователь может установить приложение и полностью сыграть локальную партию без CLI.

### Фаза 8. Coach MVP

Результат:

- подсказки по уровням;
- объяснение критических решений;
- послематчевый разбор;
- дебютная база;
- задачи из ошибок.

Критерий завершения:

- объяснения фактически не противоречат позиции и PV;
- закрыт полный учебный сценарий одной партии.

### Фаза 9. Персонализация

Результат:

- student model;
- skills breakdown;
- personal repertoire;
- spaced repetition;
- адаптивный план занятий.

### Фаза 10. Desktop release

Результат:

- Tauri package;
- установщик;
- model manager;
- offline mode;
- миграции SQLite;
- crash recovery;
- автоматические обновления при необходимости.

---

## 16. Ближайший спринт

Рекомендуемый порядок:

1. Создать модуль `arena`.
2. Определить `ArenaConfig` и формат результата.
3. Реализовать opening pairs и смену цветов.
4. Сравнить `pretrain-v1` и `selfplay-finetune-v2/step-750`.
5. Сохранять arena PGN и JSON summary.
6. Добавить arena в dashboard.
7. Добавить model registry.
8. После этого запустить более крупный self-play цикл.

Не следует начинать разработку LLM-тренера до появления структурированного Analysis API.

---

## 17. Предлагаемое разделение работы команды

### ML/Data engineer

- Dataset audit и sampling.
- Training pipeline.
- Model experiments.
- Evaluation metrics.
- Replay buffer.
- Human move model.

### Search/engine engineer

- MCTS correctness.
- Batching и profiling.
- Arena.
- Model runtime.
- UCI/engine API.
- Stockfish integration.

### Backend engineer

- Local FastAPI service.
- Game state и persistence.
- Analysis contract.
- SQLite schema.
- Jobs и model registry.

### Frontend/desktop engineer

- React board UI.
- Tauri shell.
- Game modes.
- Analysis panel.
- Coach interaction.
- Offline packaging.

### Chess content / pedagogy

- Opening knowledge base.
- Typical plans.
- Explanation templates.
- Hint ladder.
- Curriculum и exercises.
- Проверка шахматной корректности.

### QA / automation

- Rules regression.
- Engine deterministic fixtures.
- API contract tests.
- End-to-end desktop tests.
- Performance tests.
- Explanation factuality tests.

---

## 18. Основные риски

### Недоказанная сила

Policy accuracy не равна Elo. Решение: arena до дальнейших заявлений о силе.

### Медленный Python MCTS

Наивный leaf-by-leaf inference плохо использует GPU. Решение: batching и profiling до переписывания
на Rust/C++.

### Self-play collapse

Маленький replay может закреплять ошибки текущей сети. Решение: expert mix, replay window, arena,
diversity и мониторинг outcome distribution.

### Нечеловеческие уровни сложности

Ограничение simulations создаёт случайные, а не человеческие ошибки. Решение: human move model,
centipawn-loss profiles и blunder governor.

### Галлюцинации тренера

Свободный LLM может придумать нелегальный ход или ложную угрозу. Решение: grounded generation из
AnalysisResult, валидация ходов и Stockfish-oracle.

### Смешивание training и production runtime

Training checkpoint может быть несовместим с приложением. Решение: versioned model bundles и registry.

### Слишком большой scope

Движок, обучение, desktop и педагогика являются отдельными подсистемами. Решение: поэтапные MVP с
quality gates.

---

## 19. Что пока не следует обещать пользователям

- Конкретный Elo текущей сети.
- Уровень гроссмейстера.
- Человеческий стиль игры без human-rated dataset.
- Безошибочные объяснения без oracle и validation layer.
- Стабильную работу на CPU до отдельного runtime benchmark.
- Полноценное обучение «с нуля как AlphaZero» на одной GPU за короткое время.

---

## 20. Ключевые команды текущего проекта

Установка:

```powershell
python -m pip install -e ".[dev,train,dashboard]"
```

Тесты:

```powershell
python -m pytest -q
```

Аудит данных:

```powershell
python scripts/audit_dataset.py chess_data/train --max-files 3 --max-games-per-file 200
```

Supervised training:

```powershell
python scripts/train_supervised.py --steps 10000 --batch-size 256 --width 128 --blocks 10
```

Игра против checkpoint:

```powershell
python scripts/play.py runs/pretrain-v1/checkpoints/latest.pt --human-color white --sims 128
```

Self-play:

```powershell
python scripts/generate_selfplay.py runs/pretrain-v1/checkpoints/latest.pt --games 100 --sims 64
```

Dashboard:

```powershell
python dashboard/app.py
```

После запуска dashboard доступен по адресу <http://127.0.0.1:8501>.

---

## 21. Структура репозитория

```text
mlchess/
├── chess_ai/
│   ├── dataset.py       # streaming datasets, source/self-play mixtures
│   ├── encoding.py      # position/action representation
│   ├── evaluate.py      # validation metrics
│   ├── mcts.py          # PUCT search
│   ├── model.py         # policy/Q/WDL ResNet
│   ├── selfplay.py      # self-play game and replay writer
│   ├── stream.py        # PGN parsing and TrainingExample
│   └── training.py      # batch construction and losses
├── dashboard/
│   └── app.py           # local monitoring UI
├── scripts/
│   ├── audit_dataset.py
│   ├── download_official_test.py
│   ├── generate_selfplay.py
│   ├── play.py
│   ├── smoke_train.py
│   └── train_supervised.py
├── tests/
├── README.md
├── PROJECT_HANDOFF.md
└── pyproject.toml
```

---

## 22. Решения, которые считаются принятыми

- Первая версия поддерживает standard chess, не Chess960.
- Сеть всегда видит позицию от лица стороны, которая ходит.
- Policy работает только по legal moves.
- Движок и coaching layer разделены.
- Тренер не является источником шахматной истины.
- Приложение проектируется local-first.
- Checkpoint становится лучшим только после arena.
- Elo является измеренным профилем, а не маркетинговым числом.
- Дебюты и планы хранятся в knowledge base.
- Текущий Flask dashboard остаётся инструментом разработчика.
- Пользовательский игровой интерфейс будет отдельным полноценным приложением.

---

## 23. Открытые вопросы для владельца продукта и команды

1. Кто является первым целевым пользователем: новичок, игрок 1000–1400 или клубный игрок?
2. Какие первые Elo-профили обязательны для MVP?
3. Требуется ли мобильная версия или достаточно Windows desktop?
4. Допускается ли обязательная установка Stockfish вместе с приложением?
5. Нужен ли полностью автономный LLM или можно использовать облачный API для формулировок?
6. Какие языки интерфейса нужны кроме русского?
7. Нужны ли онлайн-аккаунты и синхронизация между устройствами?
8. Планируется ли multiplayer человек против человека?
9. Какой допустимый размер установщика и model bundle?
10. Какой latency на ход считается приемлемым на CPU и GPU?
11. Можно ли использовать публичные человеческие партии с рейтингами для human move model?
12. Нужны ли лицензируемые сторонние дебютные/учебные материалы?

---

## 24. Рекомендуемый запрос следующему ChatGPT

При передаче этого документа другому ChatGPT полезно дать задачу примерно в такой форме:

```text
Прочитай PROJECT_HANDOFF.md полностью. Отделяй текущее реализованное состояние от будущей
архитектуры. Подготовь детальный технический план для команды разработки MLChess.

Сначала зафиксируй допущения и открытые продуктовые вопросы. Затем разбей работу на эпики,
задачи и зависимости для ML/data, search engine, backend, frontend/desktop, QA и chess content.
Для каждой задачи укажи результат, интерфейсы, тесты, риски и definition of done.

Первым практическим этапом должен быть arena runner и model registry. Не обещай конкретный Elo,
пока не описана методика калибровки. Не позволяй LLM самостоятельно придумывать шахматные оценки:
все объяснения должны быть grounded в AnalysisResult и проверяться legal move/engine/oracle слоем.
```

---

## 25. Итог

У проекта уже есть рабочий вертикальный ML-контур:

```text
PGN.zst → streaming parser → policy/Q/WDL network → MCTS → self-play replay → fine-tune → dashboard
```

Следующая задача — превратить этот контур из экспериментального в измеряемый игровой движок.
Для этого сначала требуется arena, затем масштабное обучение и калибровка силы. После появления
стабильного Engine/Analysis API можно строить локальную игровую платформу и тренера, не связывая UI
с внутренностями PyTorch и не позволяя генеративной модели подменять шахматную логику.
