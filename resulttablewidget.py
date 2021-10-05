from PyQt5.QtWidgets import QTableView, QWidget, QVBoxLayout

from measuremodel import MeasureModel


class ResultTableWidget(QWidget):

    def __init__(self, parent=None, controller=None):
        super().__init__(parent=parent)

        self._model = MeasureModel(parent=self)
        self._table = QTableView()
        self._table.setModel(self._model)

        self._layout = QVBoxLayout()
        self._layout.addWidget(self._table)

        self.setLayout(self._layout)

        self._result = controller.result

    def updateResult(self):
        self._model.update(*self._result.get_result_table_data())
