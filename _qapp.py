"""
Helper for using PyQt4/5 (by byunghyun.ha@gmail.com)

  When imported, Python exceptions and Qt messages will be hooked and displayed
    using Qt message box.

Usage example:

    import _qapp  # This should be first that other PyQt import
    
    from PyQt4 import QtGui
    
    class MainFrame(QtGui.QMainWindow)
        SETTING_STR = ('org', 'app')
        def __init__(self):
            super().__init__()
            _qapp.setup_ui_from_design(self, 'design.ui', 'res')
            self.ui.xxx
            _qapp.setting.restore_frame_state(self, *self.SETTING_STR)
        def closeEvent(self, e):
            _qapp.setting.save_frame_state(self, *self.SETTING_STR)
            super().closeEvent(e)
        def on_open(self):
            with _qapp.setting('last-open-file', '', *self.SETTING_STR) as lof:
                args = [None, 'Choose File', lof.value, '*.xxx']
                path, _ = QtWidgets.QFileDialog.getOpenFileName(*args)  # Qt5
                if not path:
                    return
                lof.value = path
        def on_create_multiple_widget(self):
            with _qapp.hourglass():
                ui_design = load_ui_design('xxx.ui', 'yyy')
                w1, w2 = ui_design(self), ui_design(self)
        def show_message(self, title, msg):
            _qapp.msg_info(self, title, msg)  # C.f. NOTE below.
    
    _qapp.exec_(MainFrame())


TODO Hooking exception at Python secondary threads?
"""


import sys, os, traceback

# Set to use QVariant version 2. (NOTE This is only needed for Python 2 but is
#   harmless for Python 3.) If this is not set, code should be like as follows:
#     x = QtCore.QSettings(org, app).value(key, default)
#     if _v__qt4:
#         x = x.toPyObject()
import sip; sip.setapi('QVariant', 2)

# TODO Is this proper way of supporting Ctrl-C?
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

try:
    from PyQt4 import QtCore, uic
    from PyQt4.QtCore import Qt
    from PyQt4.QtGui import QApplication, QMessageBox
    _qt_version = 'PyQt4'
except ImportError:
    from PyQt5 import QtCore, uic
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication, QMessageBox
    _qt_version = 'PyQt5'


class Application(QApplication):
    """
    QApplication with message-showing function, which is used to specify main
      window even in case that sender is not in primary thread
      NOET _show_msg_with_info() below 
    """
    
    sig_call_soon = QtCore.pyqtSignal(object, object)
    
    def __init__(self, *argc):
        super(Application, self).__init__(*argc)
        self._main_window = None
        self._interactive_msg = True
        self.sig_call_soon.connect(self._invoke_function)
    
    @QtCore.pyqtSlot(object, object)
    def _invoke_function(self, callback, args):
        callback(*args)
    
    @QtCore.pyqtSlot(object, object, object, object)
    def _show_message(self, icon, title, info, msg):
        # Let our app know the situation.
        if hasattr(qapp._main_window, 'pause_for_notification'):
            qapp._main_window.pause_for_notification()
        # Show message box.
        buttons = QMessageBox.Ignore | QMessageBox.Abort
        mbox = QMessageBox(icon, title, msg, buttons, self._main_window,
                           detailedText=''.join(info))
        mbox.setEscapeButton(QMessageBox.Ignore)
        # Abort if want.
        if mbox.exec_() == QMessageBox.Abort:
            sys.exit(-1)


# Unique application instance
qapp = Application(sys.argv)

def exec_(main_win=None, interactive_msg=True):
    """
    Use interactive_msg=False to prevent appearing of dialog UI for messages.
    """
    qapp._main_window, qapp._interactive_msg = main_win, interactive_msg
    sys.exit(qapp.exec_())


def call_soon(callback, *args):
    qapp.sig_call_soon.emit(callback, args)


# Shortcut for displaying message dialogs.
#   NOTE Also consider: QtCore's qDebug, qWarning, qCritical, qFatal, qInfo (Qt5).
#    They will provide call stack trace via _show_msg_with_info() below.
msg_info = QMessageBox.information
msg_critical = QMessageBox.critical
msg_question = QMessageBox.question
msg_warning = QMessageBox.warning


def setup_ui_from_design(w, ui_file, folder='.', debug=False):
    # Change working directory, because uic supports relative path only and
    #   resource files are not handled correctly without doing it.
    old_path = os.getcwd()
    os.chdir(folder)
    # Load and set up UI.
    w.ui = uic.loadUiType(ui_file)[0]()
    w.ui.setupUi(w)  # NOTE Here, resources are loaded.
    if debug:
        uic.compileUi(ui_file, sys.stdout)  # Print UI code.
    # Change working directory back.
    os.chdir(old_path)

def load_ui_design(ui_file, folder='', debug=False):
    # CAUTION Resource cannot be loaded correctly (c.f. NOTE above).
    def factory(form_class, qt_base_class, parent):
        w = qt_base_class(parent)
        w.ui = form_class()
        w.ui.setupUi(w)
        return w
    ui_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), folder)
    old_path = os.getcwd()
    os.chdir(ui_path)
    form_class, qt_base_class = uic.loadUiType(ui_file)
    if debug:
        uic.compileUi(ui_file, sys.stdout)  # Print UI code.
    os.chdir(old_path)
    return lambda parent: factory(form_class, qt_base_class, parent)


class setting(object):
    
    def __init__(self, key, default, org, app=''):
        self.key, self.org, self.app = key, org, app
        self.value = QtCore.QSettings(org, app).value(key, default)
    
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        QtCore.QSettings(self.org, self.app).setValue(self.key, self.value)
    
    @staticmethod
    def remove(key, org, app=''):
        QtCore.QSettings(org, app).remove(key)
    
    @staticmethod
    def contains(key, org, app=''):
        return QtCore.QSettings(org, app).contains(key)
    
    @staticmethod
    def restore_widget_geom(w, key, org, app='', _d=QtCore.QByteArray()):
        w.restoreGeometry(QtCore.QSettings(org, app).value(key, _d))
    @staticmethod
    def save_widget_geom(w, key, org, app=''):
        QtCore.QSettings(org, app).setValue(key, w.saveGeometry())
    @staticmethod
    def restore_window_stat(w, key, org, app='', _d=QtCore.QByteArray()):
        w.restoreState(QtCore.QSettings(org, app).value(key, _d))
    @staticmethod
    def save_window_stat(w, key, org, app=''):
        QtCore.QSettings(org, app).setValue(key, w.saveState())
    @staticmethod
    def restore_frame_state(w, org, app=''):
        setting.restore_widget_geom(w, 'frame/geometry', org, app)
        setting.restore_window_stat(w, 'frame/state', org, app)
    @staticmethod
    def save_frame_state(w, org, app=''):
        setting.save_widget_geom(w, 'frame/geometry', org, app)
        setting.save_window_stat(w, 'frame/state', org, app)


class hourglass(object):
    
    def __init__(self, widget=None):
        self.widget = widget
    
    def __enter__(self):
        if self.widget:
            # TODO Check if correct approach.
            self.old_cursor = self.widget.cursor()
            self.widget.setCursor(Qt.WaitCursor)
        else:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        if self.widget:
            self.widget.setCursor(self.old_cursor)
        else:
            QApplication.restoreOverrideCursor()


def install_message_hooks():
    # function for signaling app to show message box.
    def _show_msg_with_info(icon, title, info, msg):
        sys.stderr.write(''.join(info))
        # Here, QMetaObject.invokeMethod() is used to call app's slot for showing
        #   message dialog. It is because i) Qt does not allow to show GUI at
        #   secondary threads and ii) invokeMethod() can suspend secondary thread.
        #   NOTE postEvent() is alternative but in that case secondary thread
        #     cannot be paused.
        #   NOTE As noted below, exceptions in Python secondary thread cannot be
        #     hooked to be here. Still the invokeMethod() is valid, however,
        #     because it does work for Qt threads.
        #   NOTE Sometimes (maybe at the end of process?) qapp becomes None,
        #     which is very surprising and strange, so we check it.
        if qapp and qapp._interactive_msg:
            # Get connection type to invoke app's slot. When calling object lives
            #   in different thread than app, it will be BlockingQueuedConnection
            #   and, as a result, the calling thread is suspended until message
            #   dialog ends. But that connection type can possibly cause deadlock if
            #   it is used for calling at the same thread. So DirectConnection is
            #   used in that case.
            ct = Qt.DirectConnection if (QtCore.QThread.currentThread() == qapp.thread()) \
                                     else Qt.BlockingQueuedConnection
            # Invoke qapp._show_message().
            QtCore.QMetaObject.invokeMethod(qapp, '_show_message', ct,
                QtCore.Q_ARG(object, icon), QtCore.Q_ARG(object, title),
                QtCore.Q_ARG(object, info), QtCore.Q_ARG(object, msg))
    # Install Python exception hook.
    #   NOTE To my regret, exception hook does not work at Python secondary
    #     threads (as of Jan 2016): https://bugs.python.org/issue1230540. 
    def _py_exc_hook(etype, value, tb):
        info = traceback.format_exception(etype, value, tb)
        msg = info[-1]
        # Provide traceback up to this point too if necessary (because sometimes
        #   exception traceback does not fully explain call stack sometimes,
        #   probably when c-extension is involved).
        tb = traceback.format_stack() 
        if len(tb) > 1:
            info.append('Stack Traceback for the above exception:\n')
            info.extend(traceback.format_stack()[:-1])
        _show_msg_with_info(QMessageBox.Critical, 'Python Exception', info, msg)
    sys.excepthook, __py_exc_hook0 = _py_exc_hook, sys.excepthook
    # Install Qt message hook. (NOTE QtSystemMsg is ignored because it is identical
    #   to QtCriticalMsg and there is no way to distinguish them at this moment.
    #   Yet, I don't know which one is better to be displayed to users.)
    if _qt_version == 'PyQt4':
        def _qt_msg_hook(mtype, msg):
            _TI = {QtCore.QtDebugMsg:    ('Debug',    QMessageBox.Information),
                   QtCore.QtWarningMsg:  ('Warning',  QMessageBox.Warning),
                   QtCore.QtCriticalMsg: ('Critical', QMessageBox.Critical),
                   QtCore.QtFatalMsg:    ('Fatal',    QMessageBox.Critical)}
            tstr, icon = _TI[mtype]
            info = traceback.format_stack()
            if len(info) > 1:
                info.insert(0, 'Stack Traceback (most recent call last):\n')
            info[-1] = 'Qt %s Message: %s\n' % (tstr, msg)
            _show_msg_with_info(icon, 'Qt %s Message' % tstr, info, info[-1])
        QtCore.qInstallMsgHandler(_qt_msg_hook)
    elif _qt_version == 'PyQt5':
        def _qt_msg_hook(mtype, context, msg):
            _TI = {QtCore.QtDebugMsg:    ('Debug',       QMessageBox.Information),
                   QtCore.QtInfoMsg:     ('Information', QMessageBox.Information),
                   QtCore.QtWarningMsg:  ('Warning',     QMessageBox.Warning),
                   QtCore.QtCriticalMsg: ('Critical',    QMessageBox.Critical),
                   QtCore.QtFatalMsg:    ('Fatal',       QMessageBox.Critical)}
            tstr, icon = _TI[mtype]
            info = traceback.format_stack()
            if len(info) > 1:
                info.insert(0, 'Stack Traceback (most recent call last):\n')
            args = (tstr, msg, context.file, context.line, context.function)
            info[-1] = 'Qt %s Message: %s (%s:%u, %s)\n' % args
            _show_msg_with_info(icon, 'Qt %s Message' % tstr, info, info[-1])
        QtCore.qInstallMessageHandler(_qt_msg_hook)
    else:
        assert False, 'It does not make sense.'

install_message_hooks()


if __name__ == '__main__':
    assert False
