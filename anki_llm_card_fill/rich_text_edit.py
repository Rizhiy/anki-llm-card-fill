from aqt.qt import QImage, QMimeData, QTextEdit


class QImageTextEdit(QTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.images = []

    def canInsertFromMimeData(self, source: QMimeData) -> bool:  # noqa: N802
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source: QMimeData) -> None:  # noqa: N802
        if source.hasImage():
            image = QImage(source.imageData())
            self.textCursor().insertImage(image)
            self.images.append(image)
        else:
            super().insertFromMimeData(source)

    def clear(self) -> None:
        super().clear()
        self.images = []
