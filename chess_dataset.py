from huggingface_hub import snapshot_download

local_dir = snapshot_download(
    repo_id="KeithG33/ChessBot-Dataset",
    repo_type="dataset",
    allow_patterns="train/*.pgn.zst",  # скачиваем только PGN-файлы из train
    local_dir="./chess_data"
)
print(f"Все файлы скачаны в: {local_dir}")