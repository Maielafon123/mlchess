# MLChess original curriculum v1

Original bilingual educational text and constructed training positions.
Content license: CC BY 4.0. Attribution: MLChess original curriculum.

The server grades legal moves and persists each student’s progress. The public
curriculum lists starting positions and learning goals; solution lines are omitted.

## opening-center

Центр и развитие

В дебюте пешки и фигуры борются за центральные поля. Развивайте лёгкие фигуры и следите за прямыми угрозами. После каждого хода соперника проверьте шахи, взятия и незащищённые фигуры. Повторный ход одной фигурой должен иметь конкретную причину, пока другие фигуры остаются на начальных полях.

Center and development

Early moves contest the central squares. Develop minor pieces and watch concrete threats. After every opposing move, check for checks, captures and undefended pieces. Repeatedly moving one piece needs a reason while other pieces remain on their starting squares.

## king-safety

Безопасность короля

Рокировка может вывести короля из центра, но не гарантирует безопасность. Король не может рокироваться из-под шаха, через шах или на атакованное поле. Учитывайте открытые линии, пешечное прикрытие и активность фигур соперника. Перед решением проверьте конкретные ответы противника.

King safety

Castling can move the king away from the center, but does not guarantee safety. Castling out of check, through check or into check is illegal. Consider open files, pawn cover and opposing piece activity. Check concrete opposing replies before deciding.

## forcing-moves

Шахи и взятия

Шах требует немедленного ответа: ухода короля, взятия атакующей фигуры или перекрытия линии. При двойном шахе возможен только ход короля. Взятие меняет материальный баланс, но не всякое взятие выгодно. Каждый ход варианта должен быть легальным и сохранять безопасность собственного короля.

Forcing moves

A check requires a king move, capture of the checking piece or block of its line. A double check can only be answered by a king move. A capture changes the material balance but is not always beneficial. Every move in a variation must be legal and leave your own king safe.

## back-rank

Мат по последней горизонтали

Король за собственными пешками иногда не имеет поля для отступления. Ладья или ферзь могут использовать открытую вертикаль и дать шах по последней горизонтали. Чтобы доказать мат, проверьте уход короля, взятие атакующей фигуры и перекрытие шаха. Самого шаха недостаточно для утверждения о мате.

Back-rank checkmate

A king behind its own pawns may have no escape square. A rook or queen can use an open file to check along the back rank. To prove checkmate, inspect king moves, captures of the checking piece and blocks. A check by itself is not proof of checkmate.

## knight-checks

Стеснённый король и конь

Конь атакует поля буквой Г и перепрыгивает через фигуры. Шах конём нельзя перекрыть. Собственные фигуры вокруг короля могут закрывать все пути отступления. Но сначала нужно проверить, можно ли взять атакующего коня и остаётся ли у короля хотя бы одно безопасное поле.

A boxed-in king and a knight

A knight attacks in an L shape and jumps over pieces. A knight check cannot be blocked. Friendly pieces around a king may close every escape route. Still check whether the knight can be captured and whether the king has any safe square.

## promotion

Превращение пешки

Пешка на последней горизонтали превращается в ферзя, ладью, слона или коня. Превращение является частью того же хода. Обычно ферзь даёт больше возможностей, но другая фигура может избегать пата или давать нужный шах. После выбора фигуры заново проверьте шах, мат и пат.

Pawn promotion

A pawn reaching the last rank becomes a queen, rook, bishop or knight. Promotion is part of the same move. A queen usually offers the most options, but another piece may avoid stalemate or give a useful check. Recheck check, checkmate and stalemate after choosing the piece.

## en-passant

Взятие на проходе

После двойного хода пешки соперника иногда возможно взятие на проходе. Оно доступно только непосредственно следующим ходом. Взятая пешка снимается с соседнего поля, а не с поля назначения вашей пешки. Как и любой ход, такое взятие не должно оставлять своего короля под шахом.

En passant

After an opposing pawn advances two squares, an en passant capture may be available. It must be made immediately on the next move. The captured pawn is removed from the adjacent square, not the destination square. As with any move, the capture must not leave your own king in check.

## draws

Мат, пат и ничья

Если легальных ходов нет и король под шахом, это мат. Если ходов нет, но шаха нет, это пат и ничья. Другие правила ничьей включают недостаточный материал и повторения. Для проверки повторений нужна история ходов: одна позиция в FEN не содержит всей необходимой информации.

Checkmate, stalemate and draws

No legal moves with the king in check means checkmate. No legal moves without check means stalemate and a draw. Other draw rules include insufficient material and repetitions. Repetition requires the game history: a FEN alone does not contain all the required information.

## Training positions

All four positions have a legal mate in one. Promotion choices that also prove
checkmate must be accepted by the server grader.

- back-rank: `6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1`
- king-diagonal: `rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2`
- knight-net: `6rk/6pp/8/6N1/8/8/8/6K1 w - - 0 1`
- promotion-finish: `7k/5Ppp/8/8/8/8/8/6K1 w - - 0 1`
