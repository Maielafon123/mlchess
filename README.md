# MLChess

[Открыть MLChess](https://95.135.208.48): партии с другом по ссылке без регистрации,
игра со Stockfish, тренер, уроки и задачи. Сайт работает в телефонном браузере.
Рейтинговый режим требует аккаунт; вход через Google на текущем IP отключён.

Веб-приложение запускается через Docker Compose. Локальный запуск описан в
[compose-runbook](infra/compose-runbook.md), развёртывание на VPS — в
[server-runbook](infra/server-runbook.md), резервное копирование — в
[recovery-runbook](infra/recovery-runbook.md). У веб-приложения отдельные
сервисы обучения и доставки событий, а вычисления Stockfish выполняют воркеры.
Последние результаты проверок и оставшиеся ограничения — в
[A_SIGNOFF](docs/integration/A_SIGNOFF.md).

## Обучаемый движок

Обучаемый policy–value движок и его данные живут отдельно от серверного
Stockfish. История этого направления описана в
[`PROJECT_HANDOFF.md`](PROJECT_HANDOFF.md).

## Что уже реализовано

- потоковое чтение обычных и Zstandard-сжатых PGN;
- фильтр Chess960 для standard-chess v1;
- 20-плоскостное каноническое представление позиции;
- AlphaZero-совместимая policy-голова на 4672 действия;
- policy/Q/WDL ResNet и legal-masked loss;
- source-balanced sampler: Lc0 70%, ChessBench 20%, puzzles 10%;
- PUCT MCTS и консольная игра против checkpoint;
- генератор MCTS self-play с компактными replay-шардами `.npz`;
- сохранение puzzle metadata (`Themes`, `Opening`, `Rating`) для будущего тренера;
- тесты рокировки, en passant, promotion, зеркального augmentation и реальных PGN-аннотаций.

## Установка

```powershell
python -m pip install -e ".[dev,train]"
```

## Проверки

```powershell
python -m pytest -q
python scripts/audit_dataset.py chess_data/train --max-files 3 --max-games-per-file 200
python scripts/smoke_train.py chess_data/train --examples 1024 --epochs 3 --width 32 --blocks 2
python scripts/train_supervised.py --steps 10000 --batch-size 256 --width 128 --blocks 10
```

`smoke_train.py` — не основной pretrain. Это короткая end-to-end проверка формата данных,
GPU, loss и backpropagation до запуска больших экспериментов.

`train_supervised.py` сохраняет `config.json`, JSONL-метрики и checkpoint'ы в отдельный каталог
`runs/`. Обучение измеряется шагами, а не «эпохами» по всему многомиллиардному train.
По умолчанию train sampler смешивает Lc0, ChessBench и puzzles в пропорции 70/20/10;
это меняется через `--source-weights` или отключается пустой строкой.

## Игра против сети

После обучения можно открыть консольную партию (пока это техническая проверка, а не
сильный шахматный бот):

```powershell
python scripts/play.py runs/pretrain-v1/checkpoints/latest.pt --human-color white --sims 128
```

Ходы принимаются в UCI (`e2e4`) или SAN (`e4`, `Nf3`). MCTS использует policy сети,
но для реальной силы сначала потребуется большой supervised pretrain и затем self-play.

## Self-play

```powershell
python scripts/generate_selfplay.py runs/pretrain-v1/checkpoints/latest.pt --games 100 --sims 64
```

Каждая партия сохраняется в `artifacts/selfplay/` вместе с canonical state,
visit-count policy и итоговой оценкой позиции. Следующий этап — подключить эти
shards к train sampler с постепенно растущей долей self-play.

## Локальный мониторинг

```powershell
python dashboard/app.py
```

Откройте `http://127.0.0.1:8501`: dashboard показывает live-метрики run'ов,
список checkpoints и число self-play партий. Страница обновляется каждые 5 секунд.

## Данные

Локальный train находится в `chess_data/train`. Официальный test скачивается отдельно:

```powershell
python scripts/download_official_test.py
```

Позиции читаются прямо из `.pgn.zst`; весь набор не распаковывается в память или в один файл.

