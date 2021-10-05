from PyQt5.QtCore import pyqtSignal, QTimer

from mytools.measurewidget import MeasureWidget, MeasureTask, CancelToken
from forgot_again.file import remove_if_exists


class MeasureWidgetWithSecondaryParameters(MeasureWidget):
    secondaryChanged = pyqtSignal(dict)

    def __init__(self, parent=None, controller=None):
        super().__init__(parent=parent, controller=controller)

        self._uiDebouncer = QTimer()
        self._uiDebouncer.setSingleShot(True)
        self._uiDebouncer.timeout.connect(self.on_debounced_gui)

        self._params = 0

        self._paramInputWidget.createWidgets(parent=self, params=self._controller.secondaryParams.required)

    def _connectSignals(self):
        self._paramInputWidget.secondaryChanged.connect(self.on_params_changed)

    def check(self):
        print('subclass checking...')
        self._modeDuringCheck()
        self._threads.start(
            MeasureTask(
                self._controller.check,
                self.checkTaskComplete,
                self._token,
                [self._selectedDevice, self._params]
            ))

    def checkTaskComplete(self):
        res = super(MeasureWidgetWithSecondaryParameters, self).checkTaskComplete()
        if not res:
            self._token = CancelToken()
        return res

    def calibrate(self, what):
        print(f'calibrating {what}...')
        self._modeDuringMeasure()
        calibrations = {
            'LO': self._controller._calibrateLO,
            'RF': self._controller._calibrateRF,
            'Mod': self._controller._calibrateMod,
        }
        self._threads.start(
            MeasureTask(
                calibrations[what],
                self.calibrateTaskComplete,
                self._token,
                [self._selectedDevice, self._params]
            ))

    def calibrateTaskComplete(self):
        print('calibrate finished')
        self._modePreMeasure()
        self.calibrateFinished.emit()

    def measure(self):
        print('subclass measuring...')
        self._modeDuringMeasure()
        self._threads.start(
            MeasureTask(
                self._controller.measure,
                self.measureTaskComplete,
                self._token,
                [self._selectedDevice, self._params]
            ))

    def measureTaskComplete(self):
        res = super(MeasureWidgetWithSecondaryParameters, self).measureTaskComplete()
        if not res:
            self._token = CancelToken()
            self._modePreCheck()
        return res

    def cancel(self):
        if not self._token.cancelled:
            if self._threads.activeThreadCount() > 0:
                print('cancelling task')
            self._token.cancelled = True

    def on_params_changed(self):
        self._uiDebouncer.start(1000)
        self.secondaryChanged.emit(self._paramInputWidget.params)

    def updateWidgets(self, params):
        self._paramInputWidget.updateWidgets(params)
        self._connectSignals()

    def on_debounced_gui(self):
        # remove_if_exists('cal_lo.ini')
        # remove_if_exists('cal_rf.ini')
        remove_if_exists('adjust.ini')
