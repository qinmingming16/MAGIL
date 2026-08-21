import sys
import re
import pyautogui
import win32api, win32con
import subprocess
import mido
import keyboard
import rtmidi
import pygame
import webbrowser
import darkdetect
import ctypes
from collections import defaultdict
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QLineEdit, QTextEdit, 
                            QComboBox, QFileDialog, QMessageBox, QPushButton, QScrollArea,
                            QVBoxLayout, QWidget, QHBoxLayout, QSizePolicy)
from PyQt5.QtCore import QThread, pyqtSignal, QObject, QMutex, QTimer, Qt, QSize
from PyQt5.QtGui import QIcon, QKeyEvent, QFont, QPixmap, QPalette

pyautogui.PAUSE = 0

NOTE_TO_KEY = {
    48: 'z', 50: 'x', 52: 'c', 53: 'v', 55: 'b', 57: 'n',59: 'm',
    60: 'a', 62: 's', 64: 'd', 65: 'f', 67: 'g', 69: 'h', 71: 'j',
    72: 'q', 74: 'w', 76: 'e', 77: 'r', 79: 't', 81: 'y', 83: 'u'
}

class CustomButton(QPushButton):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            event.ignore()
        else:
            super().keyPressEvent(event)

class WatermarkWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        watermark_text = "原琴辅助演奏4.0-Created by Qinmingming"
        
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.watermarklabel = QLabel(watermark_text, self)
        
        font = QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(14)
        font.setBold(True)
        font.setItalic(True)
        
        self.watermarklabel.setFont(font)
        self.watermarklabel.setStyleSheet("""
            QLabel {
                color: rgba(128, 128, 128, 150);
                background-color: rgba(255, 255, 255, 30);  /* 轻微白色背景 */
                padding: 5px;
                border-radius: 5px;
            }
        """)
        
        self.watermarklabel.adjustSize()
        self.resize(self.watermarklabel.size())
        
        self.move(10, 10)

class Worker(QObject):
    finished = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, file_content, p):
        super().__init__()
        self.file_content = file_content
        self.p = int(p)
        self.m = 0.0
        self.n = 0
        self.t = 0.0
        self._mutex = QMutex()
        self._abort = False

    def abort(self):
        self._mutex.lock()
        self._abort = True
        self._mutex.unlock()

    def should_abort(self):
        self._mutex.lock()
        abort = self._abort
        self._mutex.unlock()
        return abort

    def run(self):
        self.status.emit("5秒后开始演奏")
        self.thread().msleep(5000)
        
        stored_lines = [line for line in self.file_content.split('\n') if line.strip() != ""]
        
        for line in stored_lines:
            if self.should_abort():
                break
                
            if re.match(r'^-?\d+\.?\d*$', line.strip()):
                self.m = float(line.strip())
                continue
            
            separated_lines = line.strip().split('/')[:-1]
            
            for segment in separated_lines:
                if self.should_abort():
                    break
                    
                self.n = 0
                i = 0
                while i < len(segment) and not self.should_abort():
                    char = segment[i]
                    if char == '(':
                        self.n += 1
                        stack = 1
                        i += 1
                        while i < len(segment) and stack > 0 and not self.should_abort():
                            if segment[i] == '(': stack += 1
                            elif segment[i] == ')': stack -= 1
                            i += 1
                    elif char == '[':
                        self.n += 1
                        stack = 1
                        i += 1
                        while i < len(segment) and stack > 0 and not self.should_abort():
                            if segment[i] == '[': stack += 1
                            elif segment[i] == ']': stack -= 1
                            i += 1
                    else:
                        self.n += 1
                        i += 1
                
                if self.should_abort():
                    break
                    
                self.t = round(self.m / self.n, 2) if self.n != 0 else 0
                
                i = 0
                while i < len(segment) and not self.should_abort():
                    char = segment[i]
                    if char == '(':
                        stack = 1
                        start = i + 1
                        i += 1
                        while i < len(segment) and stack > 0 and not self.should_abort():
                            if segment[i] == '(': stack += 1
                            elif segment[i] == ')': stack -= 1
                            i += 1
                        if not self.should_abort():
                            keys = segment[start:i-1].replace(' ', '')
                            for key_char in list(keys):
                                (lambda c: [(r:=win32api.VkKeyScan(c)), (s:=(r>>8)&1) and win32api.keybd_event(win32con.VK_SHIFT,0,0,0), win32api.keybd_event(r&0xFF,0,0,0), win32api.keybd_event(r&0xFF,0,win32con.KEYEVENTF_KEYUP,0), s and win32api.keybd_event(win32con.VK_SHIFT,0,win32con.KEYEVENTF_KEYUP,0)])(str(key_char))
                            self.status.emit(f"按下和音: {keys}")
                            self.thread().msleep(int(self.t * 1000))
                    
                    elif char == '[':
                        stack = 1
                        i += 1
                        
                        while i < len(segment) and stack > 0 and not self.should_abort():
                            current_char = segment[i]
                            
                            if current_char == '[':
                                stack += 1
                                i += 1
                            elif current_char == ']':
                                stack -= 1
                                i += 1
                            elif current_char == '(':
                                start = i + 1
                                paren_stack = 1
                                i += 1
                                while i < len(segment) and paren_stack > 0 and not self.should_abort():
                                    if segment[i] == '(': paren_stack += 1
                                    elif segment[i] == ')': paren_stack -= 1
                                    i += 1
                                if not self.should_abort():
                                    keys = segment[start:i-1].replace(' ', '')
                                    for key_char in list(keys):
                                        (lambda c: [(r:=win32api.VkKeyScan(c)), (s:=(r>>8)&1) and win32api.keybd_event(win32con.VK_SHIFT,0,0,0), win32api.keybd_event(r&0xFF,0,0,0), win32api.keybd_event(r&0xFF,0,win32con.KEYEVENTF_KEYUP,0), s and win32api.keybd_event(win32con.VK_SHIFT,0,win32con.KEYEVENTF_KEYUP,0)])(str(key_char))
                                    self.status.emit(f"按下琶音和音: {keys}")
                                    self.thread().msleep(self.p)
                            else:
                                if not self.should_abort():
                                    (lambda c: [(r:=win32api.VkKeyScan(c)), (s:=(r>>8)&1) and win32api.keybd_event(win32con.VK_SHIFT,0,0,0), win32api.keybd_event(r&0xFF,0,0,0), win32api.keybd_event(r&0xFF,0,win32con.KEYEVENTF_KEYUP,0), s and win32api.keybd_event(win32con.VK_SHIFT,0,win32con.KEYEVENTF_KEYUP,0)])(current_char)
                                    self.status.emit(f"按下琶音: {current_char}")
                                    self.thread().msleep(self.p)
                                i += 1
                        
                        if not self.should_abort():
                            self.thread().msleep(int(self.t * 1000))
                    
                    else:
                        if not self.should_abort():
                            (lambda c: [(r:=win32api.VkKeyScan(c)), (s:=(r>>8)&1) and win32api.keybd_event(win32con.VK_SHIFT,0,0,0), win32api.keybd_event(r&0xFF,0,0,0), win32api.keybd_event(r&0xFF,0,win32con.KEYEVENTF_KEYUP,0), s and win32api.keybd_event(win32con.VK_SHIFT,0,win32con.KEYEVENTF_KEYUP,0)])(char)
                            self.status.emit(f"按下单音: {char}")
                            self.thread().msleep(int(self.t * 1000))
                            i += 1
        
        self.finished.emit('completed' if not self.should_abort() else 'uncompleted')

class Worker1(QObject):
    finished = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, file_content, b, file_name, c):
        super().__init__()
        self.file_content = file_content
        self.b = b
        self.c = float(c)
        self.file_name = file_name
        self._mutex = QMutex()
        self._abort = False

    def abort(self):
        self._mutex.lock()
        self._abort = True
        self._mutex.unlock()

    def should_abort(self):
        self._mutex.lock()
        abort = self._abort
        self._mutex.unlock()
        return abort

    def run(self):
        self.status.emit("5秒后开始演奏")
        self.thread().msleep(5000)

        if self.file_name[-4:] == '.exe':
            try:
                result = subprocess.run(self.file_name, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.status.emit("演奏完成！")
            except Exception as e:
                self.status.emit("发生错误！")
        elif self.file_name[-3:] == '.py':
            try:
                result = subprocess.run(['python', self.file_name], capture_output=True, text=True)
                self.status.emit("演奏完成！")
            except Exception as e:
                self.status.emit("发生错误！")
        elif self.file_name[-4:] == '.txt':
            self.file_content = self.file_content.replace("\n", "")
            
            p = 0
            length = len(self.file_content)

            def remove_chars(s, chars_to_remove):
                while s and s[-1] in chars_to_remove:
                    s = s[:-1]
                return s

            while p < length and  not self.should_abort():
                if p + 5 < length and self.file_content[p] == '&':

                    original_string = self.file_content[p+1:p+6]
                    chars_to_remove = "0/"
                    processed_string = remove_chars(original_string, chars_to_remove)
                    for key_char1 in processed_string:
                        (lambda c: [(r:=win32api.VkKeyScan(c)), (s:=(r>>8)&1) and win32api.keybd_event(win32con.VK_SHIFT,0,0,0), win32api.keybd_event(r&0xFF,0,0,0), win32api.keybd_event(r&0xFF,0,win32con.KEYEVENTF_KEYUP,0), s and win32api.keybd_event(win32con.VK_SHIFT,0,win32con.KEYEVENTF_KEYUP,0)])(str(key_char1))
                    self.status.emit(f"按下: {processed_string}")
                    p += 6
                    self.thread().msleep(int((self.b*self.c)*1000))
                elif p + 4 < length:

                    original_string = self.file_content[p:p+5]
                    chars_to_remove = "0/"
                    processed_string = remove_chars(original_string, chars_to_remove)
                    for key_char1 in processed_string:
                        (lambda c: [(r:=win32api.VkKeyScan(c)), (s:=(r>>8)&1) and win32api.keybd_event(win32con.VK_SHIFT,0,0,0), win32api.keybd_event(r&0xFF,0,0,0), win32api.keybd_event(r&0xFF,0,win32con.KEYEVENTF_KEYUP,0), s and win32api.keybd_event(win32con.VK_SHIFT,0,win32con.KEYEVENTF_KEYUP,0)])(str(key_char1))
                    self.status.emit(f"按下: {processed_string}")
                    p += 5
                    self.thread().msleep(int(self.b*1000))
                else:
                    break
            self.finished.emit('completed' if not self.should_abort() else 'uncompleted')

class Worker2(QObject):
    finished = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, file_content, b):
        super().__init__()
        self.file_content = file_content
        self.b = b
        self._mutex = QMutex()
        self._abort = False

    def abort(self):
        self._mutex.lock()
        self._abort = True
        self._mutex.unlock()

    def should_abort(self):
        self._mutex.lock()
        abort = self._abort
        self._mutex.unlock()
        return abort

    def process_string(self, content):
        n = len(content)
        i = 0
        buffer = []
        plus_count = 0

        while i < n and not self.should_abort():
            if content[i].isalpha():
                buffer.append(content[i])
                plus_count = 0
                i += 1
            else:
                if buffer:
                    for key_char2 in ''.join(buffer):
                        (lambda c: [(r:=win32api.VkKeyScan(c)), (s:=(r>>8)&1) and win32api.keybd_event(win32con.VK_SHIFT,0,0,0), win32api.keybd_event(r&0xFF,0,0,0), win32api.keybd_event(r&0xFF,0,win32con.KEYEVENTF_KEYUP,0), s and win32api.keybd_event(win32con.VK_SHIFT,0,win32con.KEYEVENTF_KEYUP,0)])(str(key_char2))
                    self.status.emit(f"按下: {''.join(buffer)}")
                    buffer = []

                if content[i] == '=':
                    self.thread().msleep(int(self.b))
                elif content[i] == '-':
                    self.thread().msleep(int(self.b*2))
                elif content[i] == '+':
                    self.thread().msleep(int(self.b*4))
                    plus_count += 1
                    if plus_count >= 44:
                        break
                else:
                    plus_count = 0

                i += 1

        if buffer and not self.should_abort():
            for key_char2 in ''.join(buffer):
                (lambda c: [(r:=win32api.VkKeyScan(c)), (s:=(r>>8)&1) and win32api.keybd_event(win32con.VK_SHIFT,0,0,0), win32api.keybd_event(r&0xFF,0,0,0), win32api.keybd_event(r&0xFF,0,win32con.KEYEVENTF_KEYUP,0), s and win32api.keybd_event(win32con.VK_SHIFT,0,win32con.KEYEVENTF_KEYUP,0)])(str(key_char2))
            self.status.emit(f"按下: {''.join(buffer)}")
    
    def run(self):
        self.status.emit("5秒后开始演奏")
        self.thread().msleep(5000)
        
        lines = self.file_content.split('\n')

        def is_chinese(char):
            return '\u4e00' <= char <= '\u9fff'
        
        filtered_lines = [line for line in lines if not (line and is_chinese(line[0]))]
        processed_content = '\n'.join(filtered_lines).replace("\n", "")
        
        self.process_string(processed_content)
        self.finished.emit('completed' if not self.should_abort() else 'uncompleted')

class Worker3(QObject):
    finished = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, b, file_name):
        super().__init__()
        self.file_name = file_name
        self.b = b
        self._mutex = QMutex()
        self._abort = False

    def abort(self):
        self._mutex.lock()
        self._abort = True
        self._mutex.unlock()

    def should_abort(self):
        self._mutex.lock()
        abort = self._abort
        self._mutex.unlock()
        return abort

    def run(self):
        self.status.emit("5秒后开始演奏")
        self.thread().msleep(5000)
        
        mid = mido.MidiFile(self.file_name)
        bpm = self.b
        tempo = int(60000000 / bpm * mid.ticks_per_beat / 480)
        
        for msg in mid:
            delta = mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
            if delta > 0 and not self.should_abort():
                self.thread().msleep(int(delta*1000000))
                
            if msg.type == 'note_on' and msg.velocity > 0:
                note = msg.note
                while note > 83:
                    note -= 12
                while note < 48:
                    note += 12
                
                if note in NOTE_TO_KEY and not self.should_abort():
                    (lambda c: [(r:=win32api.VkKeyScan(c)), (s:=(r>>8)&1) and win32api.keybd_event(win32con.VK_SHIFT,0,0,0), win32api.keybd_event(r&0xFF,0,0,0), win32api.keybd_event(r&0xFF,0,win32con.KEYEVENTF_KEYUP,0), s and win32api.keybd_event(win32con.VK_SHIFT,0,win32con.KEYEVENTF_KEYUP,0)])(NOTE_TO_KEY[note])
                    self.status.emit(f"按下: {NOTE_TO_KEY[note]}")
        
        self.finished.emit('completed' if not self.should_abort() else 'uncompleted')

class MainWindow(QWidget):
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MainWindow()
        return cls._instance
     
    def __init__(self):
        super().__init__()

        self.setWindowTitle('原琴辅助演奏4.0')
        self.setGeometry(20, 60, 1350, 785)

        self.setWindowIcon(QIcon('resource\\background\\秦明明16.png'))

        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        pygame.mixer.init()
        pygame.mixer.set_num_channels(84)

        try:
            self.sound001 = pygame.mixer.Sound(r'resource\Nightwind_Horn\Z.wav')
            self.sound002 = pygame.mixer.Sound(r'resource\Nightwind_Horn\X.wav')
            self.sound003 = pygame.mixer.Sound(r'resource\Nightwind_Horn\C.wav')
            self.sound004 = pygame.mixer.Sound(r'resource\Nightwind_Horn\V.wav')
            self.sound005 = pygame.mixer.Sound(r'resource\Nightwind_Horn\B.wav')
            self.sound006 = pygame.mixer.Sound(r'resource\Nightwind_Horn\N.wav')
            self.sound007 = pygame.mixer.Sound(r'resource\Nightwind_Horn\M.wav')
            self.sound008 = pygame.mixer.Sound(r'resource\Nightwind_Horn\A.wav')
            self.sound009 = pygame.mixer.Sound(r'resource\Nightwind_Horn\S.wav')
            self.sound010 = pygame.mixer.Sound(r'resource\Nightwind_Horn\D.wav')
            self.sound011 = pygame.mixer.Sound(r'resource\Nightwind_Horn\F.wav')
            self.sound012 = pygame.mixer.Sound(r'resource\Nightwind_Horn\G.wav')
            self.sound013 = pygame.mixer.Sound(r'resource\Nightwind_Horn\H.wav')
            self.sound014 = pygame.mixer.Sound(r'resource\Nightwind_Horn\J.wav')
        except Exception as e:
            QMessageBox.warning(self, '警告', '音频加载失败！')

        self.Label1 = QLabel('《原琴辅助演奏4.0-winx64》，在旅途', self)
        self.Label1.setFixedSize(1000, 60)
        self.Label1.move(160, 80)
        font = QFont("微软雅黑", 30)
        font.setBold(True)
        font.setItalic(True)
        self.Label1.setFont(font)
        
        self.yz1 = CustomButton("开始演奏",self)
        self.yz1.clicked.connect(self.start_processing)
        self.yz1.move(630, 430)
        self.yz1.resize(90, 30)
        self.yz1.setFont(QFont("微软雅黑", 14))
        
        self.yz2 = CustomButton("停止演奏",self)
        self.yz2.clicked.connect(self.stop_processing)
        self.yz2.setEnabled(False)
        self.yz2.move(740, 430)
        self.yz2.resize(90, 30)
        self.yz2.setFont(QFont("微软雅黑", 14))
        
        self.yz3 = CustomButton('屏幕测量',self)
        self.yz3.move(520, 430)
        self.yz3.resize(90, 30)
        self.yz3.clicked.connect(self.yz3p)
        self.yz3.setFont(QFont("微软雅黑", 14))

        self.yz4 = CustomButton('选择文件',self)
        self.yz4.move(740, 300)
        self.yz4.resize(90, 30)
        self.yz4.clicked.connect(self.yz4p)
        self.yz4.setFont(QFont("微软雅黑", 10))

        self.yz5 = QLabel('输入琴谱路径',self)
        self.yz5.move(160, 300)
        self.yz5.setFont(QFont("微软雅黑", 10))

        self.yz6 = QLabel('输入音距(建筑谱)',self)
        self.yz6.setFixedWidth(600)
        self.yz6.move(160, 350)
        self.yz6.setFont(QFont("微软雅黑", 10))

        self.yz7 = QLabel('(支持浮点数、整数，单位s)',self)
        self.yz7.setFixedWidth(600)
        self.yz7.move(740, 350)
        self.yz7.setFont(QFont("微软雅黑", 10))

        self.yz8 = QLineEdit(self)
        self.yz8.move(300, 300)
        self.yz8.resize(420, 30)
        self.yz8.setFont(QFont("微软雅黑", 8))

        self.yz9 = QLineEdit(self)
        self.yz9.move(300, 350)
        self.yz9.resize(420, 30)
        self.yz9.setFont(QFont("微软雅黑", 8))

        self.yz10 = QLabel('',self)
        self.yz10.setFixedWidth(600)
        self.yz10.move(160, 250)
        self.yz10.setFont(QFont("微软雅黑", 10))

        self.yz11 = QComboBox(self)
        self.yz11.addItems(["编译规则:建筑谱及可执行", "编译规则:指尖/刻师傅谱", "编译规则:呱呱谱", "编译规则:MIDI谱"])
        self.yz11.currentIndexChanged.connect(self.yz11p)
        self.yz11.move(160, 430)
        self.yz11.resize(200, 30)
        self.yz11.setFont(QFont("微软雅黑", 10))

        self.dh1 = CustomButton(self)
        self.dh1.setFixedSize(60, 60)
        self.dh1.clicked.connect(self.dh1p)
        self.dh1.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.dh1)
        self.dh1.setIcon(QIcon(r'resource\Icon\Home.png'))
        self.dh1.setIconSize(QSize(55, 55))

        self.dh2 = CustomButton(self)
        self.dh2.setFixedSize(60, 60)
        self.dh2.clicked.connect(self.dh2p)
        self.dh2.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.dh2)
        self.dh2.setIcon(QIcon(r'resource\Icon\Auto.png'))
        self.dh2.setIconSize(QSize(55, 55))

        self.dh3 = CustomButton(self)
        self.dh3.setFixedSize(60, 60)
        self.dh3.clicked.connect(self.dh3p)
        self.dh3.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.dh3)
        self.dh3.setIcon(QIcon(r'resource\Icon\Edit.png'))
        self.dh3.setIconSize(QSize(55, 55))

        self.dh4 = CustomButton(self)
        self.dh4.setFixedSize(60, 60)
        self.dh4.clicked.connect(self.dh4p)
        self.dh4.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.dh4)
        self.dh4.setIcon(QIcon(r'resource\Icon\Key.png'))
        self.dh4.setIconSize(QSize(55, 55))

        self.dh5 = CustomButton(self)
        self.dh5.setFixedSize(60, 60)
        self.dh5.clicked.connect(self.dh5p)
        self.dh5.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.dh5)
        self.dh5.setIcon(QIcon(r'resource\Icon\Midi.png'))
        self.dh5.setIconSize(QSize(55, 55))

        self.dh6 = CustomButton(self)
        self.dh6.setFixedSize(60, 60)
        self.dh6.clicked.connect(self.dh6p)
        self.dh6.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.dh6)
        self.dh6.setIcon(QIcon(r'resource\Icon\Piano.png'))
        self.dh6.setIconSize(QSize(55, 55))

        self.dh7 = CustomButton(self)
        self.dh7.setFixedSize(60, 60)
        self.dh7.clicked.connect(self.dh7p)
        self.dh7.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(self.dh7)
        self.dh7.setIcon(QIcon(r'resource\Icon\Setting.png'))
        self.dh7.setIconSize(QSize(55, 55))

        self.bj1 = CustomButton('追加新行', self)
        self.bj1.move(960, 510)
        self.bj1.resize(90, 30)
        self.bj1.clicked.connect(self.bj1p)
        self.bj1.setFont(QFont("微软雅黑", 14))

        self.bj2 = CustomButton('向行覆写', self)
        self.bj2.move(1070, 510)
        self.bj2.resize(90, 30)
        self.bj2.clicked.connect(self.bj2p)
        self.bj2.setFont(QFont("微软雅黑", 14))

        self.bj3 = QLineEdit(self)
        self.bj3.move(160, 300)
        self.bj3.resize(60, 50)
        self.bj3.setFont(QFont("微软雅黑", 8))

        self.bj4 = QLineEdit(self)
        self.bj4.move(230, 300)
        self.bj4.resize(60, 50)
        self.bj4.setFont(QFont("微软雅黑", 8))

        self.bj5 = QLineEdit(self)
        self.bj5.move(300, 300)
        self.bj5.resize(60, 50)
        self.bj5.setFont(QFont("微软雅黑", 8))

        self.bj6 = QLineEdit(self)
        self.bj6.move(370, 300)
        self.bj6.resize(60, 50)
        self.bj6.setFont(QFont("微软雅黑", 8))

        self.bj7 = QLineEdit(self)
        self.bj7.move(440, 300)
        self.bj7.resize(60, 50)
        self.bj7.setFont(QFont("微软雅黑", 8))

        self.bj8 = QLineEdit(self)
        self.bj8.move(510, 300)
        self.bj8.resize(60, 50)
        self.bj8.setFont(QFont("微软雅黑", 8))

        self.bj9 = QLineEdit(self)
        self.bj9.move(580, 300)
        self.bj9.resize(60, 50)
        self.bj9.setFont(QFont("微软雅黑", 8))

        self.bj10 = QLineEdit(self)
        self.bj10.move(650, 300)
        self.bj10.resize(60, 50)
        self.bj10.setFont(QFont("微软雅黑", 8))

        self.bj11 = QLineEdit(self)
        self.bj11.move(720, 300)
        self.bj11.resize(60, 50)
        self.bj11.setFont(QFont("微软雅黑", 8))

        self.bj12 = QLineEdit(self)
        self.bj12.move(790, 300)
        self.bj12.resize(60, 50)
        self.bj12.setFont(QFont("微软雅黑", 8))

        self.bj13 = QLineEdit(self)
        self.bj13.move(860, 300)
        self.bj13.resize(60, 50)
        self.bj13.setFont(QFont("微软雅黑", 8))

        self.bj14 = QLineEdit(self)
        self.bj14.move(930, 300)
        self.bj14.resize(60, 50)
        self.bj14.setFont(QFont("微软雅黑", 8))

        self.bj15 = QLineEdit(self)
        self.bj15.move(1000, 300)
        self.bj15.resize(60, 50)
        self.bj15.setFont(QFont("微软雅黑", 8))

        self.bj16 = QLineEdit(self)
        self.bj16.move(1070, 300)
        self.bj16.resize(60, 50)
        self.bj16.setFont(QFont("微软雅黑", 8))

        self.bj17 = QLineEdit(self)
        self.bj17.move(1140, 300)
        self.bj17.resize(60, 50)
        self.bj17.setFont(QFont("微软雅黑", 8))

        self.bj18 = QLineEdit(self)
        self.bj18.move(1210, 300)
        self.bj18.resize(60, 50)
        self.bj18.setFont(QFont("微软雅黑", 8))

        self.bj19 = QLineEdit(self)
        self.bj19.move(160, 360)
        self.bj19.resize(60, 50)
        self.bj19.setFont(QFont("微软雅黑", 8))

        self.bj20 = QLineEdit(self)
        self.bj20.move(230, 360)
        self.bj20.resize(60, 50)
        self.bj20.setFont(QFont("微软雅黑", 8))

        self.bj21 = QLineEdit(self)
        self.bj21.move(300, 360)
        self.bj21.resize(60, 50)
        self.bj21.setFont(QFont("微软雅黑", 8))

        self.bj22 = QLineEdit(self)
        self.bj22.move(370, 360)
        self.bj22.resize(60, 50)
        self.bj22.setFont(QFont("微软雅黑", 8))

        self.bj23 = QLineEdit(self)
        self.bj23.move(440, 360)
        self.bj23.resize(60, 50)
        self.bj23.setFont(QFont("微软雅黑", 8))

        self.bj24 = QLineEdit(self)
        self.bj24.move(510, 360)
        self.bj24.resize(60, 50)
        self.bj24.setFont(QFont("微软雅黑", 8))

        self.bj25= QLineEdit(self)
        self.bj25.move(580, 360)
        self.bj25.resize(60, 50)
        self.bj25.setFont(QFont("微软雅黑", 8))

        self.bj26 = QLineEdit(self)
        self.bj26.move(650, 360)
        self.bj26.resize(60, 50)
        self.bj26.setFont(QFont("微软雅黑", 8))

        self.bj27 = QLineEdit(self)
        self.bj27.move(720, 360)
        self.bj27.resize(60, 50)
        self.bj27.setFont(QFont("微软雅黑", 8))

        self.bj28 = QLineEdit(self)
        self.bj28.move(790, 360)
        self.bj28.resize(60, 50)
        self.bj28.setFont(QFont("微软雅黑", 8))

        self.bj29 = QLineEdit(self)
        self.bj29.move(860, 360)
        self.bj29.resize(60, 50)
        self.bj29.setFont(QFont("微软雅黑", 8))

        self.bj30 = QLineEdit(self)
        self.bj30.move(930, 360)
        self.bj30.resize(60, 50)
        self.bj30.setFont(QFont("微软雅黑", 8))

        self.bj31 = QLineEdit(self)
        self.bj31.move(1000, 360)
        self.bj31.resize(60, 50)
        self.bj31.setFont(QFont("微软雅黑", 8))

        self.bj32 = QLineEdit(self)
        self.bj32.move(1070, 360)
        self.bj32.resize(60, 50)
        self.bj32.setFont(QFont("微软雅黑", 8))

        self.bj33 = QLineEdit(self)
        self.bj33.move(1140, 360)
        self.bj33.resize(60, 50)
        self.bj33.setFont(QFont("微软雅黑", 8))

        self.bj34 = QLineEdit(self)
        self.bj34.move(1210, 360)
        self.bj34.resize(60, 50)
        self.bj34.setFont(QFont("微软雅黑", 8))

        self.bj35 = QLineEdit(self)
        self.bj35.move(260, 460)
        self.bj35.resize(160, 30)
        self.bj35.setFont(QFont("微软雅黑", 8))

        self.bj36 = QLabel('覆写/追加行数', self)
        self.bj36.move(160, 460)
        self.bj36.setFont(QFont("微软雅黑", 10))

        self.bj37 = CustomButton('向行追加', self)
        self.bj37.move(1180, 510)
        self.bj37.resize(90, 30)
        self.bj37.clicked.connect(self.bj37p)
        self.bj37.setFont(QFont("微软雅黑", 14))

        self.bj38 = CustomButton('建筑谱临时编辑', self)
        self.bj38.move(160, 220)
        self.bj38.resize(180, 50)
        self.bj38.clicked.connect(self.bj38p)
        self.bj38.setFont(QFont("微软雅黑", 14))

        self.bj39 = CustomButton('琴谱替换', self)
        self.bj39.move(360, 220)
        self.bj39.resize(180, 50)
        self.bj39.clicked.connect(self.bj39p)
        self.bj39.setFont(QFont("微软雅黑", 14))

        self.bj40 = QTextEdit(self)
        self.bj40.move(160, 300)
        self.bj40.resize(400, 400)
        self.bj40.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.bj40.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.bj40.setPlaceholderText('输入需替换的琴谱内容')
        self.bj40.setFont(QFont("微软雅黑", 8))

        self.bj41 = QTextEdit(self)
        self.bj41.move(600, 300)
        self.bj41.resize(400, 400)
        self.bj41.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.bj41.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.bj41.setPlaceholderText('替换结果')
        self.bj41.setFont(QFont("微软雅黑", 8))

        self.bj42 = CustomButton('替换', self)
        self.bj42.move(1160, 480)
        self.bj42.resize(90, 30)
        self.bj42.clicked.connect(self.bj42p)
        self.bj42.setFont(QFont("微软雅黑", 14))

        self.bj43 = QLabel('替换规则：', self)
        self.bj43.move(1050, 260)
        self.bj43.setFont(QFont("微软雅黑", 10))

        self.bj44 = CustomButton('清空', self)
        self.bj44.move(1050, 480)
        self.bj44.resize(90, 30)
        self.bj44.clicked.connect(self.bj44p)
        self.bj44.setFont(QFont("微软雅黑", 14))

        self.bj45 = CustomButton('清空', self)
        self.bj45.move(1180, 220)
        self.bj45.resize(90, 50)
        self.bj45.clicked.connect(self.bj45p)
        self.bj45.setFont(QFont("微软雅黑", 14))

        self.bj46 = CustomButton('选择文件', self)
        self.bj46.move(960, 460)
        self.bj46.resize(90, 30)
        self.bj46.clicked.connect(self.bj46p)
        self.bj46.setFont(QFont("微软雅黑", 10))

        self.bj47 = QLineEdit(self)
        self.bj47.move(530, 460)
        self.bj47.resize(420, 30)
        self.bj47.setFont(QFont("微软雅黑", 8))
        
        self.bj48 = QLabel('输入琴谱路径', self)
        self.bj48.move(440, 460)
        self.bj48.setFont(QFont("微软雅黑", 10))

        self.bj49 = QTextEdit(self)
        self.bj49.move(1050, 300)
        self.bj49.resize(200, 60)
        self.bj49.setPlaceholderText('输入需替换的字符')
        self.bj49.setFont(QFont("微软雅黑", 8))

        self.bj50 = QTextEdit(self)
        self.bj50.move(1050, 400)
        self.bj50.resize(200, 60)
        self.bj50.setPlaceholderText('输入替换为的字符')
        self.bj50.setFont(QFont("微软雅黑", 8))

        self.bj51 = QLabel('', self)
        self.bj51.setFixedWidth(600)
        self.bj51.move(160, 170)
        self.bj51.setFont(QFont("微软雅黑", 10))

        self.jy1 = QLabel('输入映射规则（例如：a -> b）', self)
        self.jy1.setFixedWidth(600)
        self.jy1.move(160, 260)
        self.jy1.setFont(QFont("微软雅黑", 10))

        self.jy2 = QComboBox(self)
        self.jy2.addItems(["原键:a", "原键:b", "原键:c", "原键:d", "原键:e", "原键:f", "原键:g", "原键:h", "原键:i", "原键:j", "原键:k", "原键:l", "原键:m",
            "原键:n", "原键:o", "原键:p", "原键:q", "原键:r", "原键:s", "原键:t", "原键:u", "原键:v", "原键:w", "原键:x", "原键:y", "原键:z",
            "原键:0", "原键:1", "原键:2", "原键:3", "原键:4", "原键:5", "原键:6", "原键:7", "原键:8", "原键:9",
            "原键:f1", "原键:f2", "原键:f3", "原键:f4", "原键:f5", "原键:f6", "原键:f7", "原键:f8", "原键:f9", "原键:f10", "原键:f11", "原键:f12",
            "原键:space", "原键:enter", "原键:esc", "原键:tab", "原键:backspace", "原键:shift", "原键:ctrl", "原键:alt", "原键:up", "原键:down", "原键:left", "原键:right",
            "原键:insert", "原键:delete", "原键:home", "原键:end", "原键:pageup", "原键:pagedown"])
        self.jy2.currentIndexChanged.connect(self.jy2p)
        self.jy2.move(160, 300)
        self.jy2.resize(560, 30)
        self.jy2.setFont(QFont("微软雅黑", 10))

        self.jy3 = QComboBox(self)
        self.jy3.addItems(["目标键:a", "目标键:b", "目标键:c", "目标键:d", "目标键:e", "目标键:f", "目标键:g", "目标键:h", "目标键:i", "目标键:j", "目标键:k", "目标键:l", "目标键:m",
            "目标键:n", "目标键:o", "目标键:p", "目标键:q", "目标键:r", "目标键:s", "目标键:t", "目标键:u", "目标键:v", "目标键:w", "目标键:x", "目标键:y", "目标键:z",
            "目标键:0", "目标键:1", "目标键:2", "目标键:3", "目标键:4", "目标键:5", "目标键:6", "目标键:7", "目标键:8", "目标键:9",
            "目标键:f1", "目标键:f2", "目标键:f3", "目标键:f4", "目标键:f5", "目标键:f6", "目标键:f7", "目标键:f8", "目标键:f9", "目标键:f10", "目标键:f11", "目标键:f12",
            "目标键:space", "目标键:enter", "目标键:esc", "目标键:tab", "目标键:backspace", "目标键:shift", "目标键:ctrl", "目标键:alt", "目标键:up", "目标键:down", "目标键:left", "目标键:right",
            "目标键:insert", "目标键:delete", "目标键:home", "目标键:end", "目标键:pageup", "目标键:pagedown"])
        
        self.jy3.currentIndexChanged.connect(self.jy3p)
        self.jy3.move(160, 350)
        self.jy3.resize(560, 30)
        self.jy3.setFont(QFont("微软雅黑", 10))

        self.jy4 = CustomButton('映射', self)
        self.jy4.clicked.connect(self.map_keys)
        self.jy4.move(520, 430)
        self.jy4.resize(90, 30)
        self.jy4.setFont(QFont("微软雅黑", 14))

        self.jy5 = CustomButton('取消映射', self)
        self.jy5.clicked.connect(self.unmap_keys)
        self.jy5.move(630, 430)
        self.jy5.resize(90, 30)
        self.jy5.setFont(QFont("微软雅黑", 14))

        self.jy6 = QLabel('', self)
        self.jy6.setFixedWidth(600)
        self.jy6.move(160, 230)
        self.jy6.setFont(QFont("微软雅黑", 10))

        self.jy7 = CustomButton('清空映射', self)
        self.jy7.clicked.connect(self.unmap_all_keys)
        self.jy7.move(740, 430)
        self.jy7.resize(90, 30)
        self.jy7.setFont(QFont("微软雅黑", 14))

        self.my1 = QComboBox(self)
        self.my1.move(300, 300)
        self.my1.resize(420, 30)
        self.my1.setFont(QFont("微软雅黑", 10))

        self.my2 = QLabel('接入MIDI设备', self)
        self.my2.move(160, 300)
        self.my2.setFont(QFont("微软雅黑", 10))

        self.my3 = QComboBox(self)
        self.my3.addItems(["映射规则:风物之诗琴-基础21键", "映射规则:风物之诗琴-36转21键", "映射规则:风物之诗琴-拓展36键", "映射规则:风物之诗琴-60转21键",
                           "映射规则:风物之诗琴-拓展60键", "映射规则:镜花之琴-基础21键", "映射规则:镜花之琴-36转21键", "映射规则:镜花之琴-拓展36键",
                           "映射规则:镜花之琴-60转21键", "映射规则:镜花之琴-拓展60键", "映射规则:老旧的诗琴-基础21键", "映射规则:老旧的诗琴-36转21键",
                           "映射规则:老旧的诗琴-拓展36键", "映射规则:老旧的诗琴-60转21键", "映射规则:老旧的诗琴-拓展60键", "映射规则:晚风圆号-基础14键",
                           "映射规则:悠可琴-基础21键", "映射规则:悠可琴-31转21键", "映射规则:悠可琴-拓展31键", "映射规则:悠可琴-43转21键","映射规则:悠可琴-拓展43键",
                           "映射规则:「余音」-基础21键", "映射规则:「余音」-31转21键", "映射规则:「余音」-拓展31键", "映射规则:「余音」-43转21键","映射规则:「余音」-拓展43键",
                           "映射规则:跃律琴-基础21键", "映射规则:跃律琴-36转21键", "映射规则:跃律琴-拓展36键", "映射规则:跃律琴-60转21键",
                           "映射规则:跃律琴-拓展60键", "映射规则:钢琴-增强拓展21键", "映射规则:钢琴-增强拓展60键"])
        self.my3.currentIndexChanged.connect(self.my3p)
        self.my3.move(300, 350)
        self.my3.resize(420, 30)
        self.my3.setFont(QFont("微软雅黑", 10))

        self.my4 = QLabel('输入映射规则', self)
        self.my4.move(160, 350)
        self.my4.setFont(QFont("微软雅黑", 10))

        self.my5 = CustomButton('开始映射', self)
        self.my5.clicked.connect(self.start_midi_mapping)
        self.my5.move(630, 430)
        self.my5.resize(90, 30)
        self.my5.setFont(QFont("微软雅黑", 14))

        self.my6 = CustomButton('停止映射', self)
        self.my6.clicked.connect(self.stop_midi_mapping)
        self.my6.move(740, 430)
        self.my6.resize(90, 30)
        self.my6.setFont(QFont("微软雅黑", 14))
        self.my6.setEnabled(False)

        self.my7 = CustomButton('刷新', self)
        self.my7.clicked.connect(self.refresh_midi_devices)
        self.my7.move(740, 300)
        self.my7.resize(90, 30)
        self.my7.setFont(QFont("微软雅黑", 14))

        self.my8 = QLabel('', self)
        self.my8.setFixedWidth(600)
        self.my8.move(160, 230)
        self.my8.setFont(QFont("微软雅黑", 10))

        self.mn1 = CustomButton('', self)
        self.mn1.move(302, 285)
        self.mn1.setFixedSize(86, 86)
        self.mn1.clicked.connect(self.mn1p)

        self.mn2 = CustomButton('', self)
        self.mn2.move(427, 285)
        self.mn2.setFixedSize(86, 86)
        self.mn2.clicked.connect(self.mn2p)

        self.mn3 = CustomButton('', self)
        self.mn3.move(552, 285)
        self.mn3.setFixedSize(86, 86)
        self.mn3.clicked.connect(self.mn3p)

        self.mn4 = CustomButton('', self)
        self.mn4.move(677, 285)
        self.mn4.setFixedSize(86, 86)
        self.mn4.clicked.connect(self.mn4p)

        self.mn5 = CustomButton('', self)
        self.mn5.move(802, 285)
        self.mn5.setFixedSize(86, 86)
        self.mn5.clicked.connect(self.mn5p)

        self.mn6 = CustomButton('', self)
        self.mn6.move(927, 285)
        self.mn6.setFixedSize(86, 86)
        self.mn6.clicked.connect(self.mn6p)

        self.mn7 = CustomButton('', self)
        self.mn7.move(1052, 285)
        self.mn7.setFixedSize(86, 86)
        self.mn7.clicked.connect(self.mn7p)

        self.mn8 = CustomButton('', self)
        self.mn8.move(302, 387)
        self.mn8.setFixedSize(86, 86)
        self.mn8.clicked.connect(self.mn8p)

        self.mn9 = CustomButton('', self)
        self.mn9.move(427, 387)
        self.mn9.setFixedSize(86, 86)
        self.mn9.clicked.connect(self.mn9p)

        self.mn10 = CustomButton('', self)
        self.mn10.move(552, 387)
        self.mn10.setFixedSize(86, 86)
        self.mn10.clicked.connect(self.mn10p)

        self.mn11 = CustomButton('', self)
        self.mn11.move(677, 387)
        self.mn11.setFixedSize(86, 86)
        self.mn11.clicked.connect(self.mn11p)

        self.mn12 = CustomButton('', self)
        self.mn12.move(802, 387)
        self.mn12.setFixedSize(86, 86)
        self.mn12.clicked.connect(self.mn12p)

        self.mn13 = CustomButton('', self)
        self.mn13.move(927, 387)
        self.mn13.setFixedSize(86, 86)
        self.mn13.clicked.connect(self.mn13p)

        self.mn14 = CustomButton('', self)
        self.mn14.move(1052, 387)
        self.mn14.setFixedSize(86, 86)
        self.mn14.clicked.connect(self.mn14p)

        self.mn15 = CustomButton('', self)
        self.mn15.move(302, 489)
        self.mn15.setFixedSize(86, 86)
        self.mn15.clicked.connect(self.mn15p)

        self.mn16 = CustomButton('', self)
        self.mn16.move(427, 489)
        self.mn16.setFixedSize(86, 86)
        self.mn16.clicked.connect(self.mn16p)

        self.mn17 = CustomButton('', self)
        self.mn17.move(552, 489)
        self.mn17.setFixedSize(86, 86)
        self.mn17.clicked.connect(self.mn17p)

        self.mn18 = CustomButton('', self)
        self.mn18.move(677, 489)
        self.mn18.setFixedSize(86, 86)
        self.mn18.clicked.connect(self.mn18p)

        self.mn19 = CustomButton('', self)
        self.mn19.move(802, 489)
        self.mn19.setFixedSize(86, 86)
        self.mn19.clicked.connect(self.mn19p)

        self.mn20 = CustomButton('', self)
        self.mn20.move(927, 489)
        self.mn20.setFixedSize(86, 86)
        self.mn20.clicked.connect(self.mn20p)

        self.mn21 = CustomButton('', self)
        self.mn21.move(1052, 489)
        self.mn21.setFixedSize(86, 86)
        self.mn21.clicked.connect(self.mn21p)

        self.mn22 = CustomButton('', self)
        self.mn22.move(302, 591)
        self.mn22.setFixedSize(86, 86)
        self.mn22.clicked.connect(self.mn22p)

        self.mn23 = CustomButton('', self)
        self.mn23.move(427, 591)
        self.mn23.setFixedSize(86, 86)
        self.mn23.clicked.connect(self.mn23p)

        self.mn24 = CustomButton('', self)
        self.mn24.move(552, 591)
        self.mn24.setFixedSize(86, 86)
        self.mn24.clicked.connect(self.mn24p)

        self.mn25 = CustomButton('', self)
        self.mn25.move(677, 591)
        self.mn25.setFixedSize(86, 86)
        self.mn25.clicked.connect(self.mn25p)

        self.mn26 = CustomButton('', self)
        self.mn26.move(802, 591)
        self.mn26.setFixedSize(86, 86)
        self.mn26.clicked.connect(self.mn26p)

        self.mn27 = CustomButton('', self)
        self.mn27.move(927, 591)
        self.mn27.setFixedSize(86, 86)
        self.mn27.clicked.connect(self.mn27p)

        self.mn28 = CustomButton('', self)
        self.mn28.move(1052, 591)
        self.mn28.setFixedSize(86, 86)
        self.mn28.clicked.connect(self.mn28p)

        self.mn29 = CustomButton('', self)
        self.mn29.move(302, 693)
        self.mn29.setFixedSize(86, 86)
        self.mn29.clicked.connect(self.mn29p)

        self.mn30 = CustomButton('', self)
        self.mn30.move(427, 693)
        self.mn30.setFixedSize(86, 86)
        self.mn30.clicked.connect(self.mn30p)

        self.mn31 = CustomButton('', self)
        self.mn31.move(552, 693)
        self.mn31.setFixedSize(86, 86)
        self.mn31.clicked.connect(self.mn31p)

        self.mn32 = CustomButton('', self)
        self.mn32.move(677, 693)
        self.mn32.setFixedSize(86, 86)
        self.mn32.clicked.connect(self.mn32p)

        self.mn33 = CustomButton('', self)
        self.mn33.move(802, 693)
        self.mn33.setFixedSize(86, 86)
        self.mn33.clicked.connect(self.mn33p)

        self.mn34 = CustomButton('', self)
        self.mn34.move(927, 693)
        self.mn34.setFixedSize(86, 86)
        self.mn34.clicked.connect(self.mn34p)

        self.mn35 = CustomButton('', self)
        self.mn35.move(1052, 693)
        self.mn35.setFixedSize(86, 86)
        self.mn35.clicked.connect(self.mn35p)

        self.mn36 = CustomButton('', self)
        self.mn36.move(388, 285)
        self.mn36.setFixedSize(39, 43)
        self.mn36.clicked.connect(self.mn36p)

        self.mn37 = CustomButton('', self)
        self.mn37.move(513, 285)
        self.mn37.setFixedSize(39, 43)
        self.mn37.clicked.connect(self.mn37p)

        self.mn38 = CustomButton('', self)
        self.mn38.move(763, 285)
        self.mn38.setFixedSize(39, 43)
        self.mn38.clicked.connect(self.mn38p)

        self.mn39 = CustomButton('', self)
        self.mn39.move(888, 285)
        self.mn39.setFixedSize(39, 43)
        self.mn39.clicked.connect(self.mn39p)

        self.mn40 = CustomButton('', self)
        self.mn40.move(1013, 285)
        self.mn40.setFixedSize(39, 43)
        self.mn40.clicked.connect(self.mn40p)

        self.mn41 = CustomButton('', self)
        self.mn41.move(388, 387)
        self.mn41.setFixedSize(39, 43)
        self.mn41.clicked.connect(self.mn41p)

        self.mn42 = CustomButton('', self)
        self.mn42.move(513, 387)
        self.mn42.setFixedSize(39, 43)
        self.mn42.clicked.connect(self.mn42p)

        self.mn43 = CustomButton('', self)
        self.mn43.move(763, 387)
        self.mn43.setFixedSize(39, 43)
        self.mn43.clicked.connect(self.mn43p)

        self.mn44 = CustomButton('', self)
        self.mn44.move(888, 387)
        self.mn44.setFixedSize(39, 43)
        self.mn44.clicked.connect(self.mn44p)

        self.mn45 = CustomButton('', self)
        self.mn45.move(1013, 387)
        self.mn45.setFixedSize(39, 43)
        self.mn45.clicked.connect(self.mn45p)

        self.mn46 = CustomButton('', self)
        self.mn46.move(388, 489)
        self.mn46.setFixedSize(39, 43)
        self.mn46.clicked.connect(self.mn46p)

        self.mn47 = CustomButton('', self)
        self.mn47.move(513, 489)
        self.mn47.setFixedSize(39, 43)
        self.mn47.clicked.connect(self.mn47p)

        self.mn48 = CustomButton('', self)
        self.mn48.move(763, 489)
        self.mn48.setFixedSize(39, 43)
        self.mn48.clicked.connect(self.mn48p)

        self.mn49 = CustomButton('', self)
        self.mn49.move(888, 489)
        self.mn49.setFixedSize(39, 43)
        self.mn49.clicked.connect(self.mn49p)

        self.mn50 = CustomButton('', self)
        self.mn50.move(1013, 489)
        self.mn50.setFixedSize(39, 43)
        self.mn50.clicked.connect(self.mn50p)

        self.mn51 = CustomButton('', self)
        self.mn51.move(388, 591)
        self.mn51.setFixedSize(39, 43)
        self.mn51.clicked.connect(self.mn51p)

        self.mn52 = CustomButton('', self)
        self.mn52.move(513, 591)
        self.mn52.setFixedSize(39, 43)
        self.mn52.clicked.connect(self.mn52p)

        self.mn53 = CustomButton('', self)
        self.mn53.move(763, 591)
        self.mn53.setFixedSize(39, 43)
        self.mn53.clicked.connect(self.mn53p)

        self.mn54 = CustomButton('', self)
        self.mn54.move(888, 591)
        self.mn54.setFixedSize(39, 43)
        self.mn54.clicked.connect(self.mn54p)

        self.mn55 = CustomButton('', self)
        self.mn55.move(1013, 591)
        self.mn55.setFixedSize(39, 43)
        self.mn55.clicked.connect(self.mn55p)

        self.mn56 = CustomButton('', self)
        self.mn56.move(388, 693)
        self.mn56.setFixedSize(39, 43)
        self.mn56.clicked.connect(self.mn56p)

        self.mn57 = CustomButton('', self)
        self.mn57.move(513, 693)
        self.mn57.setFixedSize(39, 43)
        self.mn57.clicked.connect(self.mn57p)

        self.mn58 = CustomButton('', self)
        self.mn58.move(763, 693)
        self.mn58.setFixedSize(39, 43)
        self.mn58.clicked.connect(self.mn58p)

        self.mn59 = CustomButton('', self)
        self.mn59.move(888, 693)
        self.mn59.setFixedSize(39, 43)
        self.mn59.clicked.connect(self.mn59p)

        self.mn60 = CustomButton('', self)
        self.mn60.move(1013, 693)
        self.mn60.setFixedSize(39, 43)
        self.mn60.clicked.connect(self.mn60p)

        self.mn61 = CustomButton('', self)
        self.mn61.move(302, 489)
        self.mn61.setFixedSize(86, 86)
        self.mn61.setIcon(QIcon(r'resource\Nightwind_Horn\wA.png'))
        self.mn61.setIconSize(QSize(80, 80))
        self.mn61.pressed.connect(self.sound008.play)
        self.mn61.released.connect(lambda: self.sound008.fadeout(500))

        self.mn62 = CustomButton('', self)
        self.mn62.move(427, 489)
        self.mn62.setFixedSize(86, 86)
        self.mn62.setIcon(QIcon(r'resource\Nightwind_Horn\wS.png'))
        self.mn62.setIconSize(QSize(80, 80))
        self.mn62.pressed.connect(self.sound009.play)
        self.mn62.released.connect(lambda: self.sound009.fadeout(500))

        self.mn63 = CustomButton('', self)
        self.mn63.move(552, 489)
        self.mn63.setFixedSize(86, 86)
        self.mn63.setIcon(QIcon(r'resource\Nightwind_Horn\wD.png'))
        self.mn63.setIconSize(QSize(80, 80))
        self.mn63.pressed.connect(self.sound010.play)
        self.mn63.released.connect(lambda: self.sound010.fadeout(500))

        self.mn64 = CustomButton('', self)
        self.mn64.move(677, 489)
        self.mn64.setFixedSize(86, 86)
        self.mn64.setIcon(QIcon(r'resource\Nightwind_Horn\wF.png'))
        self.mn64.setIconSize(QSize(80, 80))
        self.mn64.pressed.connect(self.sound011.play)
        self.mn64.released.connect(lambda: self.sound011.fadeout(500))

        self.mn65 = CustomButton('', self)
        self.mn65.move(802, 489)
        self.mn65.setFixedSize(86, 86)
        self.mn65.setIcon(QIcon(r'resource\Nightwind_Horn\wG.png'))
        self.mn65.setIconSize(QSize(80, 80))
        self.mn65.pressed.connect(self.sound012.play)
        self.mn65.released.connect(lambda: self.sound012.fadeout(500))

        self.mn66 = CustomButton('', self)
        self.mn66.move(927, 489)
        self.mn66.setFixedSize(86, 86)
        self.mn66.setIcon(QIcon(r'resource\Nightwind_Horn\wH.png'))
        self.mn66.setIconSize(QSize(80, 80))
        self.mn66.pressed.connect(self.sound013.play)
        self.mn66.released.connect(lambda: self.sound013.fadeout(500))

        self.mn67 = CustomButton('', self)
        self.mn67.move(1052, 489)
        self.mn67.setFixedSize(86, 86)
        self.mn67.setIcon(QIcon(r'resource\Nightwind_Horn\wJ.png'))
        self.mn67.setIconSize(QSize(80, 80))
        self.mn67.pressed.connect(self.sound014.play)
        self.mn67.released.connect(lambda: self.sound014.fadeout(500))

        self.mn68 = CustomButton('', self)
        self.mn68.move(302, 591)
        self.mn68.setFixedSize(86, 86)
        self.mn68.setIcon(QIcon(r'resource\Nightwind_Horn\wA.png'))
        self.mn68.setIconSize(QSize(80, 80))
        self.mn68.pressed.connect(self.sound001.play)
        self.mn68.released.connect(lambda: self.sound001.fadeout(500))

        self.mn69 = CustomButton('', self)
        self.mn69.move(427, 591)
        self.mn69.setFixedSize(86, 86)
        self.mn69.setIcon(QIcon(r'resource\Nightwind_Horn\wS.png'))
        self.mn69.setIconSize(QSize(80, 80))
        self.mn69.pressed.connect(self.sound002.play)
        self.mn69.released.connect(lambda: self.sound002.fadeout(500))

        self.mn70 = CustomButton('', self)
        self.mn70.move(552, 591)
        self.mn70.setFixedSize(86, 86)
        self.mn70.setIcon(QIcon(r'resource\Nightwind_Horn\wD.png'))
        self.mn70.setIconSize(QSize(80, 80))
        self.mn70.pressed.connect(self.sound003.play)
        self.mn70.released.connect(lambda: self.sound003.fadeout(500))

        self.mn71 = CustomButton('', self)
        self.mn71.move(677, 591)
        self.mn71.setFixedSize(86, 86)
        self.mn71.setIcon(QIcon(r'resource\Nightwind_Horn\wF.png'))
        self.mn71.setIconSize(QSize(80, 80))
        self.mn71.pressed.connect(self.sound004.play)
        self.mn71.released.connect(lambda: self.sound004.fadeout(500))

        self.mn72 = CustomButton('', self)
        self.mn72.move(802, 591)
        self.mn72.setFixedSize(86, 86)
        self.mn72.setIcon(QIcon(r'resource\Nightwind_Horn\wG.png'))
        self.mn72.setIconSize(QSize(80, 80))
        self.mn72.pressed.connect(self.sound005.play)
        self.mn72.released.connect(lambda: self.sound005.fadeout(500))

        self.mn73 = CustomButton('', self)
        self.mn73.move(927, 591)
        self.mn73.setFixedSize(86, 86)
        self.mn73.setIcon(QIcon(r'resource\Nightwind_Horn\wH.png'))
        self.mn73.setIconSize(QSize(80, 80))
        self.mn73.pressed.connect(self.sound006.play)
        self.mn73.released.connect(lambda: self.sound006.fadeout(500))

        self.mn74 = CustomButton('', self)
        self.mn74.move(1052, 591)
        self.mn74.setFixedSize(86, 86)
        self.mn74.setIcon(QIcon(r'resource\Nightwind_Horn\wJ.png'))
        self.mn74.setIconSize(QSize(80, 80))
        self.mn74.pressed.connect(self.sound007.play)
        self.mn74.released.connect(lambda: self.sound007.fadeout(500))

        self.mn75 = QComboBox(self)
        self.mn75.addItems(["乐器:风物之诗琴", "乐器:镜花之琴", "乐器:绮筵之鼓", "乐器:老旧的诗琴", "乐器:晚风圆号", "乐器:悠可琴", "乐器:聚聚鼓", "乐器:「余音」", "乐器:跃律琴", "乐器:钢琴"])
        self.mn75.currentIndexChanged.connect(self.mn75p)
        self.mn75.move(90, 320)
        self.mn75.resize(200, 30)
        self.mn75.setFont(QFont("微软雅黑", 10))

        self.mn76 = QComboBox(self)
        self.mn76.move(90, 390)
        self.mn76.resize(200, 30)
        self.mn76.setFont(QFont("微软雅黑", 10))

        self.mn77 = CustomButton('刷新', self)
        self.mn77.clicked.connect(self.refresh_midi_devices)
        self.mn77.move(230, 430)
        self.mn77.resize(60, 30)
        self.mn77.setFont(QFont("微软雅黑", 14))

        self.mn78 = CustomButton("开始映射", self)
        self.mn78.move(90, 470)
        self.mn78.resize(90, 30)
        self.mn78.clicked.connect(self.start_mn_mapping)
        self.mn78.setFont(QFont("微软雅黑", 14))
        self.mn78.setEnabled(True)
        
        self.mn79 = CustomButton("停止映射", self)
        self.mn79.move(200, 470)
        self.mn79.resize(90, 30)
        self.mn79.clicked.connect(self.stop_mn_mapping)
        self.mn79.setFont(QFont("微软雅黑", 14))
        self.mn79.setEnabled(False)

        self.mn80 = QLineEdit(self)
        self.mn80.move(90, 550)
        self.mn80.resize(200, 30)
        self.mn80.setFont(QFont("微软雅黑", 8))

        self.mn81 = QComboBox(self)
        self.mn81.addItems(["4/4", "3/4"])
        self.mn81.currentIndexChanged.connect(self.mn81p)
        self.mn81.move(90, 610)
        self.mn81.resize(200, 30)
        self.mn81.setFont(QFont("微软雅黑", 10))

        self.mn82 = CustomButton("启动", self)
        self.mn82.move(90, 690)
        self.mn82.resize(90, 30)
        self.mn82.clicked.connect(self.start_playback)
        self.mn82.setFont(QFont("微软雅黑", 14))
        self.mn82.setEnabled(True)
        
        self.mn83 = CustomButton("停止", self)
        self.mn83.move(200, 690)
        self.mn83.resize(90, 30)
        self.mn83.clicked.connect(self.stop_playback)
        self.mn83.setFont(QFont("微软雅黑", 14))
        self.mn83.setEnabled(False)

        self.mn84 = QLabel('', self)
        self.mn84.setFixedWidth(600)
        self.mn84.move(90, 260)
        self.mn84.setFont(QFont("微软雅黑", 10))

        self.mn85 = QLabel('乐器选择', self)
        self.mn85.setFixedWidth(100)
        self.mn85.move(90, 285)
        self.mn85.setFont(QFont("微软雅黑", 10))
        
        self.mn86 = QLabel('接入MIDI设备', self)
        self.mn86.setFixedWidth(100)
        self.mn86.move(90, 360)
        self.mn86.setFont(QFont("微软雅黑", 10))

        self.mn87 = QLabel('节拍器BPM', self)
        self.mn87.setFixedWidth(100)
        self.mn87.move(90, 520)
        self.mn87.setFont(QFont("微软雅黑", 10))

        self.mn88 = QLabel('节拍器拍号', self)
        self.mn88.setFixedWidth(100)
        self.mn88.move(90, 580)
        self.mn88.setFont(QFont("微软雅黑", 10))

        self.sz1 = QLabel('UI风格', self)
        self.sz1.move(160, 300)
        self.sz1.setFont(QFont("微软雅黑", 10))

        self.sz2 = QComboBox(self)
        self.sz2.move(220, 300)
        self.sz2.addItems(["跟随系统", "风青", "岩黄", "雷紫", "草绿", "水蓝", "火红"])
        self.sz2.resize(200, 30)
        self.sz2.currentIndexChanged.connect(self.sz2p)
        self.sz2.setFont(QFont("微软雅黑", 10))

        self.sz3 = QLabel('自动演奏', self)
        self.sz3.move(160, 400)
        self.sz3.setFont(QFont("微软雅黑", 10))

        self.sz4 = QLabel('建筑谱连音音距倍率', self)
        self.sz4.setFixedWidth(600)
        self.sz4.move(220, 400)
        self.sz4.setFont(QFont("微软雅黑", 10))

        self.sz5 = QLineEdit(self)
        self.sz5.move(350, 400)
        self.sz5.resize(70, 30)
        self.sz5.setFont(QFont("微软雅黑", 8))

        self.sz6 = CustomButton('保存', self)
        self.sz6.move(430, 450)
        self.sz6.resize(50, 30)
        self.sz6.clicked.connect(self.sz6p)
        self.sz6.setFont(QFont("微软雅黑", 10))

        self.sz7 = QLabel('琶音时间间隔', self)
        self.sz7.move(220, 450)
        self.sz7.setFont(QFont("微软雅黑", 10))

        self.sz8 = QLineEdit(self)
        self.sz8.move(350, 450)
        self.sz8.resize(70, 30)
        self.sz8.setFont(QFont("微软雅黑", 8))

        self.sz9 = QLabel('水印声明', self)
        self.sz9.move(160, 520)
        self.sz9.setFont(QFont("微软雅黑", 10))

        self.sz10 = CustomButton('开', self)
        self.sz10.move(220, 520)
        self.sz10.resize(90, 30)
        self.sz10.clicked.connect(self.sz10p)
        self.sz10.setFont(QFont("微软雅黑", 10))

        self.sz11 = CustomButton('关', self)
        self.sz11.move(330, 520)
        self.sz11.resize(90, 30)
        self.sz11.clicked.connect(self.sz11p)
        self.sz11.setFont(QFont("微软雅黑", 10))
        self.sz11.setEnabled(False)

        self.sy1 = CustomButton('使用说明', self)
        self.sy1.move(160, 380)
        self.sy1.resize(200, 220)
        self.sy1.clicked.connect(self.sy1p)
        self.sy1.setFont(QFont("微软雅黑", 14))

        self.sy2 = CustomButton('交流反馈', self)
        self.sy2.move(380, 380)
        self.sy2.resize(200, 220)
        self.sy2.clicked.connect(self.sy2p)
        self.sy2.setFont(QFont("微软雅黑", 14))

        self.sy3 = CustomButton('退出程序', self)
        self.sy3.move(600, 380)
        self.sy3.resize(200, 220)
        self.sy3.clicked.connect(self.sy3p)
        self.sy3.setFont(QFont("微软雅黑", 14))

        self.setObjectName("MainWindow")
        if darkdetect.theme() == 'Light':
            self.setStyleSheet("QWidget#MainWindow { background-color: white; }")
            self.Label1.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.yz5.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.yz6.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.yz7.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.yz10.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.bj36.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.bj43.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.bj48.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.bj51.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.jy1.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.jy6.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.my2.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.my4.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.my8.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.mn84.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.mn85.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.mn86.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.mn87.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.mn88.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.sz1.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.sz3.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.sz4.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.sz7.setStyleSheet(f'color: rgb(0, 0, 0);')
            self.sz9.setStyleSheet(f'color: rgb(0, 0, 0);')
        if darkdetect.theme() == 'Dark':
            self.setStyleSheet("QWidget#MainWindow { background-color: rgb(41, 42, 45); }")
            self.Label1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz5.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz10.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj36.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj43.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj48.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj51.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my2.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my8.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn84.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn85.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn86.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn87.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn88.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz3.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz9.setStyleSheet(f'color: rgb(255, 255, 255);')

        self.backgroundlabel = QLabel(self)
        self.backgroundlabel.setAlignment(Qt.AlignCenter)
        self.backgroundlabel.setGeometry(0, 0, self.width(), self.height())
        self.backgroundlabel.lower()

        layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.setContentsMargins(5, 0, 0, 0)
        
        with open(r'resource\setting\background.txt', 'r', encoding='utf-8') as file:
            self.background_read = file.read()

        with open(r'resource\setting\p.txt', 'r', encoding='utf-8') as file:
            self.p = file.read()

        with open(r'resource\setting\c.txt', 'r', encoding='utf-8') as file:
            self.c = file.read()

        if self.background_read == None:
            self.sz2.setCurrentIndex(0)
        if self.background_read == 'Mondstadt':
            self.sz2.setCurrentIndex(1)
        if self.background_read == 'Liyue':
            self.sz2.setCurrentIndex(2)
        if self.background_read == 'Inazuma':
            self.sz2.setCurrentIndex(3)
        if self.background_read == 'Sumeru':
            self.sz2.setCurrentIndex(4)
        if self.background_read == 'Fontaine':
            self.sz2.setCurrentIndex(5)
        if self.background_read == 'Natlan':
            self.sz2.setCurrentIndex(6)

        self.sz5.setText(self.c)
        self.sz8.setText(self.p)

        self.worker = None
        self.thread = None
        self.worker1 = None
        self.thread1 = None
        self.worker2 = None
        self.thread2 = None
        self.worker3 = None
        self.thread3 = None
        self.file_content = None
        self.file_name = None
        self.b = 0
        self.score_type = 'jianzhu'
        self.mn_listener = 0
        self.watermark = None

        try:
            self.sound36 = pygame.mixer.Sound(r'resource\Windsong_Lyre\,.wav')
            self.sound37 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#,.wav')
            self.sound38 = pygame.mixer.Sound(r'resource\Windsong_Lyre\..wav')
            self.sound39 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#..wav')
            self.sound40 = pygame.mixer.Sound(r'resource\Windsong_Lyre\xie.wav')
            self.sound41 = pygame.mixer.Sound(r'resource\Windsong_Lyre\;.wav')
            self.sound42 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#;.wav')
            self.sound43 = pygame.mixer.Sound(r'resource\Windsong_Lyre\'.wav')
            self.sound44 = pygame.mixer.Sound('resource\\Windsong_Lyre\\#\'.wav')
            self.sound45 = pygame.mixer.Sound(r'resource\Windsong_Lyre\[.wav')
            self.sound46 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#[.wav')
            self.sound47 = pygame.mixer.Sound(r'resource\Windsong_Lyre\].wav')
            self.sound49 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Z.wav')
            self.sound51 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#X.wav')
            self.sound52 = None
            self.sound54 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#V.wav')
            self.sound56 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#B.wav')
            self.sound58 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#N.wav')
            self.sound59 = None
            self.sound61 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#A.wav')
            self.sound63 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#S.wav')
            self.sound64 = None
            self.sound66 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#F.wav')
            self.sound68 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#G.wav')
            self.sound70 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#H.wav')
            self.sound71 = None
            self.sound73 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Q.wav')
            self.sound74 = None
            self.sound75 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#W.wav')
            self.sound76 = None
            self.sound78 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#R.wav')
            self.sound80 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#T.wav')
            self.sound81 = None
            self.sound82 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Y.wav')
            self.sound83 = None
            self.sound84 = pygame.mixer.Sound(r'resource\Windsong_Lyre\1.wav')
            self.sound85 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#1.wav')
            self.sound86 = pygame.mixer.Sound(r'resource\Windsong_Lyre\2.wav')
            self.sound87 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#2.wav')
            self.sound88 = pygame.mixer.Sound(r'resource\Windsong_Lyre\3.wav')
            self.sound89 = pygame.mixer.Sound(r'resource\Windsong_Lyre\4.wav')
            self.sound90 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#4.wav')
            self.sound91 = pygame.mixer.Sound(r'resource\Windsong_Lyre\5.wav')
            self.sound92 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#5.wav')
            self.sound93 = pygame.mixer.Sound(r'resource\Windsong_Lyre\6.wav')
            self.sound94 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#6.wav')
            self.sound95 = pygame.mixer.Sound(r'resource\Windsong_Lyre\7.wav')
        except Exception as e:
            QMessageBox.warning(self, '警告', '音频加载失败！')

        try:
            self.sound036 = pygame.mixer.Sound(r'resource\Windsong_Lyre\,.wav')
            self.sound037 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#,.wav')
            self.sound038 = pygame.mixer.Sound(r'resource\Windsong_Lyre\..wav')
            self.sound039 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#..wav')
            self.sound040 = pygame.mixer.Sound(r'resource\Windsong_Lyre\xie.wav')
            self.sound041 = pygame.mixer.Sound(r'resource\Windsong_Lyre\;.wav')
            self.sound042 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#;.wav')
            self.sound043 = pygame.mixer.Sound(r'resource\Windsong_Lyre\'.wav')
            self.sound044 = pygame.mixer.Sound('resource\\Windsong_Lyre\\#\'.wav')
            self.sound045 = pygame.mixer.Sound(r'resource\Windsong_Lyre\[.wav')
            self.sound046 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#[.wav')
            self.sound047 = pygame.mixer.Sound(r'resource\Windsong_Lyre\].wav')
            self.sound048 = pygame.mixer.Sound(r'resource\Windsong_Lyre\Z.wav')
            self.sound049 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Z.wav')
            self.sound050 = pygame.mixer.Sound(r'resource\Windsong_Lyre\X.wav')
            self.sound051 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#X.wav')
            self.sound052 = pygame.mixer.Sound(r'resource\Windsong_Lyre\C.wav')
            self.sound053 = pygame.mixer.Sound(r'resource\Windsong_Lyre\V.wav')
            self.sound054 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#V.wav')
            self.sound055 = pygame.mixer.Sound(r'resource\Windsong_Lyre\B.wav')
            self.sound056 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#B.wav')
            self.sound057 = pygame.mixer.Sound(r'resource\Windsong_Lyre\N.wav')
            self.sound058 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#N.wav')
            self.sound059 = pygame.mixer.Sound(r'resource\Windsong_Lyre\M.wav')
            self.sound060 = pygame.mixer.Sound(r'resource\Windsong_Lyre\A.wav')
            self.sound061 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#A.wav')
            self.sound062 = pygame.mixer.Sound(r'resource\Windsong_Lyre\S.wav')
            self.sound063 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#S.wav')
            self.sound064 = pygame.mixer.Sound(r'resource\Windsong_Lyre\D.wav')
            self.sound065 = pygame.mixer.Sound(r'resource\Windsong_Lyre\F.wav')
            self.sound066 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#F.wav')
            self.sound067 = pygame.mixer.Sound(r'resource\Windsong_Lyre\G.wav')
            self.sound068 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#G.wav')
            self.sound069 = pygame.mixer.Sound(r'resource\Windsong_Lyre\H.wav')
            self.sound070 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#H.wav')
            self.sound071 = pygame.mixer.Sound(r'resource\Windsong_Lyre\J.wav')
            self.sound072 = pygame.mixer.Sound(r'resource\Windsong_Lyre\Q.wav')
            self.sound073 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Q.wav')
            self.sound074 = pygame.mixer.Sound(r'resource\Windsong_Lyre\W.wav')
            self.sound075 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#W.wav')
            self.sound076 = pygame.mixer.Sound(r'resource\Windsong_Lyre\E.wav')
            self.sound077 = pygame.mixer.Sound(r'resource\Windsong_Lyre\R.wav')
            self.sound078 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#R.wav')
            self.sound079 = pygame.mixer.Sound(r'resource\Windsong_Lyre\T.wav')
            self.sound080 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#T.wav')
            self.sound081 = pygame.mixer.Sound(r'resource\Windsong_Lyre\Y.wav')
            self.sound082 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Y.wav')
            self.sound083 = pygame.mixer.Sound(r'resource\Windsong_Lyre\U.wav')
            self.sound084 = pygame.mixer.Sound(r'resource\Windsong_Lyre\1.wav')
            self.sound085 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#1.wav')
            self.sound086 = pygame.mixer.Sound(r'resource\Windsong_Lyre\2.wav')
            self.sound087 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#2.wav')
            self.sound088 = pygame.mixer.Sound(r'resource\Windsong_Lyre\3.wav')
            self.sound089 = pygame.mixer.Sound(r'resource\Windsong_Lyre\4.wav')
            self.sound090 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#4.wav')
            self.sound091 = pygame.mixer.Sound(r'resource\Windsong_Lyre\5.wav')
            self.sound092 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#5.wav')
            self.sound093 = pygame.mixer.Sound(r'resource\Windsong_Lyre\6.wav')
            self.sound094 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#6.wav')
            self.sound095 = pygame.mixer.Sound(r'resource\Windsong_Lyre\7.wav')
        except Exception as e:
            QMessageBox.warning(self, '警告', '音频加载失败！')

        try:
            self.sound0001 = pygame.mixer.Sound(r'resource\Metronome\I.wav')
            self.sound0002 = pygame.mixer.Sound(r'resource\Metronome\O.wav')
        except Exception as e:
            QMessageBox.warning(self, '警告', '音频加载失败！')

        try:
            self.sound0f = pygame.mixer.Sound(r'resource\Windsong_Lyre\0f.wav')
            self.sound0g = pygame.mixer.Sound(r'resource\Djem_Djem_Drum\0g.wav')
            self.sound0h = pygame.mixer.Sound(r'resource\Festive_Drum\0h.wav')
            self.sound0j = pygame.mixer.Sound(r'resource\Floral_Zither\0j.wav')
            self.sound0k = pygame.mixer.Sound(r'resource\Ukulele\0k.wav')
            self.sound0l = pygame.mixer.Sound(r'resource\Vintage_Lyre\0l.wav')
            self.sound0s = pygame.mixer.Sound(r'resource\Lingering_Euphonia\0s.wav')
            self.sound0w = pygame.mixer.Sound(r'resource\Nightwind_Horn\0w.wav')
            self.sound0y = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\0y.wav')
        except Exception as e:
            QMessageBox.warning(self, '警告', '音频加载失败！')

        self.sequence = [0, 1, 1, 1]
        self.current_index = 0
        self.timer_interval = 500
        self.mn_bpm = 50

        self.mn_timer = QTimer(self)
        self.mn_timer.timeout.connect(self.play_next)

        self.presets = {
            "映射规则:风物之诗琴-基础21键": {
                48: {"type": "key", "value": 'z'},
                50: {"type": "key", "value": 'x'},
                52: {"type": "key", "value": 'c'},
                53: {"type": "key", "value": 'v'},
                55: {"type": "key", "value": 'b'},
                57: {"type": "key", "value": 'n'},
                59: {"type": "key", "value": 'm'},
                60: {"type": "key", "value": 'a'},
                62: {"type": "key", "value": 's'},
                64: {"type": "key", "value": 'd'},
                65: {"type": "key", "value": 'f'},
                67: {"type": "key", "value": 'g'},
                69: {"type": "key", "value": 'h'},
                71: {"type": "key", "value": 'j'},
                72: {"type": "key", "value": 'q'},
                74: {"type": "key", "value": 'w'},
                76: {"type": "key", "value": 'e'},
                77: {"type": "key", "value": 'r'},
                79: {"type": "key", "value": 't'},
                81: {"type": "key", "value": 'y'},
                83: {"type": "key", "value": 'u'}
            },
            "映射规则:风物之诗琴-36转21键": {
                48: {"type": "key", "value": 'z'},
                49: {"type": "key", "value": 'x'},
                50: {"type": "key", "value": 'x'},
                51: {"type": "key", "value": 'c'},
                52: {"type": "key", "value": 'c'},
                53: {"type": "key", "value": 'v'},
                54: {"type": "key", "value": 'b'},
                55: {"type": "key", "value": 'b'},
                56: {"type": "key", "value": 'n'},
                57: {"type": "key", "value": 'n'},
                58: {"type": "key", "value": 'm'},
                59: {"type": "key", "value": 'm'},
                60: {"type": "key", "value": 'a'},
                61: {"type": "key", "value": 's'},
                62: {"type": "key", "value": 's'},
                63: {"type": "key", "value": 'd'},
                64: {"type": "key", "value": 'd'},
                65: {"type": "key", "value": 'f'},
                66: {"type": "key", "value": 'g'},
                67: {"type": "key", "value": 'g'},
                68: {"type": "key", "value": 'h'},
                69: {"type": "key", "value": 'h'},
                70: {"type": "key", "value": 'j'},
                71: {"type": "key", "value": 'j'},
                72: {"type": "key", "value": 'q'},
                73: {"type": "key", "value": 'w'},
                74: {"type": "key", "value": 'w'},
                75: {"type": "key", "value": 'e'},
                76: {"type": "key", "value": 'e'},
                77: {"type": "key", "value": 'r'},
                78: {"type": "key", "value": 't'},
                79: {"type": "key", "value": 't'},
                80: {"type": "key", "value": 'y'},
                81: {"type": "key", "value": 'y'},
                82: {"type": "key", "value": 'u'},
                83: {"type": "key", "value": 'u'}
            },
            "映射规则:风物之诗琴-拓展36键": {
                48: {"type": "key", "value": 'z'},
                49: {"type": "audio", "value": self.sound49},
                50: {"type": "key", "value": 'x'},
                51: {"type": "audio", "value": self.sound51},
                52: {"type": "key", "value": 'c'},
                53: {"type": "key", "value": 'v'},
                54: {"type": "audio", "value": self.sound54},
                55: {"type": "key", "value": 'b'},
                56: {"type": "audio", "value": self.sound56},
                57: {"type": "key", "value": 'n'},
                58: {"type": "audio", "value": self.sound58},
                59: {"type": "key", "value": 'm'},
                60: {"type": "key", "value": 'a'},
                61: {"type": "audio", "value": self.sound61},
                62: {"type": "key", "value": 's'},
                63: {"type": "audio", "value": self.sound63},
                64: {"type": "key", "value": 'd'},
                65: {"type": "key", "value": 'f'},
                66: {"type": "audio", "value": self.sound66},
                67: {"type": "key", "value": 'g'},
                68: {"type": "audio", "value": self.sound68},
                69: {"type": "key", "value": 'h'},
                70: {"type": "audio", "value": self.sound70},
                71: {"type": "key", "value": 'j'},
                72: {"type": "key", "value": 'q'},
                73: {"type": "audio", "value": self.sound73},
                74: {"type": "key", "value": 'w'},
                75: {"type": "audio", "value": self.sound75},
                76: {"type": "key", "value": 'e'},
                77: {"type": "key", "value": 'r'},
                78: {"type": "audio", "value": self.sound78},
                79: {"type": "key", "value": 't'},
                80: {"type": "audio", "value": self.sound80},
                81: {"type": "key", "value": 'y'},
                82: {"type": "audio", "value": self.sound82},
                83: {"type": "key", "value": 'u'}
            },
            "映射规则:风物之诗琴-60转21键": {
                36: {"type": "key", "value": 'z'},
                37: {"type": "key", "value": 'x'},
                38: {"type": "key", "value": 'x'},
                39: {"type": "key", "value": 'c'},
                40: {"type": "key", "value": 'c'},
                41: {"type": "key", "value": 'v'},
                42: {"type": "key", "value": 'b'},
                43: {"type": "key", "value": 'b'},
                44: {"type": "key", "value": 'n'},
                45: {"type": "key", "value": 'n'},
                46: {"type": "key", "value": 'm'},
                47: {"type": "key", "value": 'm'},
                48: {"type": "key", "value": 'z'},
                49: {"type": "key", "value": 'x'},
                50: {"type": "key", "value": 'x'},
                51: {"type": "key", "value": 'c'},
                52: {"type": "key", "value": 'c'},
                53: {"type": "key", "value": 'v'},
                54: {"type": "key", "value": 'b'},
                55: {"type": "key", "value": 'b'},
                56: {"type": "key", "value": 'n'},
                57: {"type": "key", "value": 'n'},
                58: {"type": "key", "value": 'm'},
                59: {"type": "key", "value": 'm'},
                60: {"type": "key", "value": 'a'},
                61: {"type": "key", "value": 's'},
                62: {"type": "key", "value": 's'},
                63: {"type": "key", "value": 'd'},
                64: {"type": "key", "value": 'd'},
                65: {"type": "key", "value": 'f'},
                66: {"type": "key", "value": 'g'},
                67: {"type": "key", "value": 'g'},
                68: {"type": "key", "value": 'h'},
                69: {"type": "key", "value": 'h'},
                70: {"type": "key", "value": 'j'},
                71: {"type": "key", "value": 'j'},
                72: {"type": "key", "value": 'q'},
                73: {"type": "key", "value": 'w'},
                74: {"type": "key", "value": 'w'},
                75: {"type": "key", "value": 'e'},
                76: {"type": "key", "value": 'e'},
                77: {"type": "key", "value": 'r'},
                78: {"type": "key", "value": 't'},
                79: {"type": "key", "value": 't'},
                80: {"type": "key", "value": 'y'},
                81: {"type": "key", "value": 'y'},
                82: {"type": "key", "value": 'u'},
                83: {"type": "key", "value": 'u'},
                84: {"type": "key", "value": 'q'},
                85: {"type": "key", "value": 'w'},
                86: {"type": "key", "value": 'w'},
                87: {"type": "key", "value": 'e'},
                88: {"type": "key", "value": 'e'},
                89: {"type": "key", "value": 'r'},
                90: {"type": "key", "value": 't'},
                91: {"type": "key", "value": 't'},
                92: {"type": "key", "value": 'y'},
                93: {"type": "key", "value": 'y'},
                94: {"type": "key", "value": 'u'},
                95: {"type": "key", "value": 'u'}
            },
            "映射规则:风物之诗琴-拓展60键": {
                36: {"type": "audio", "value": self.sound36},
                37: {"type": "audio", "value": self.sound37},
                38: {"type": "audio", "value": self.sound38},
                39: {"type": "audio", "value": self.sound39},
                40: {"type": "audio", "value": self.sound40},
                41: {"type": "audio", "value": self.sound41},
                42: {"type": "audio", "value": self.sound42},
                43: {"type": "audio", "value": self.sound43},
                44: {"type": "audio", "value": self.sound44},
                45: {"type": "audio", "value": self.sound45},
                46: {"type": "audio", "value": self.sound46},
                47: {"type": "audio", "value": self.sound47},
                48: {"type": "key", "value": 'z'},
                49: {"type": "audio", "value": self.sound49},
                50: {"type": "key", "value": 'x'},
                51: {"type": "audio", "value": self.sound51},
                52: {"type": "key", "value": 'c'},
                53: {"type": "key", "value": 'v'},
                54: {"type": "audio", "value": self.sound54},
                55: {"type": "key", "value": 'b'},
                56: {"type": "audio", "value": self.sound56},
                57: {"type": "key", "value": 'n'},
                58: {"type": "audio", "value": self.sound58},
                59: {"type": "key", "value": 'm'},
                60: {"type": "key", "value": 'a'},
                61: {"type": "audio", "value": self.sound61},
                62: {"type": "key", "value": 's'},
                63: {"type": "audio", "value": self.sound63},
                64: {"type": "key", "value": 'd'},
                65: {"type": "key", "value": 'f'},
                66: {"type": "audio", "value": self.sound66},
                67: {"type": "key", "value": 'g'},
                68: {"type": "audio", "value": self.sound68},
                69: {"type": "key", "value": 'h'},
                70: {"type": "audio", "value": self.sound70},
                71: {"type": "key", "value": 'j'},
                72: {"type": "key", "value": 'q'},
                73: {"type": "audio", "value": self.sound73},
                74: {"type": "key", "value": 'w'},
                75: {"type": "audio", "value": self.sound75},
                76: {"type": "key", "value": 'e'},
                77: {"type": "key", "value": 'r'},
                78: {"type": "audio", "value": self.sound78},
                79: {"type": "key", "value": 't'},
                80: {"type": "audio", "value": self.sound80},
                81: {"type": "key", "value": 'y'},
                82: {"type": "audio", "value": self.sound82},
                83: {"type": "key", "value": 'u'},
                84: {"type": "audio", "value": self.sound84},
                85: {"type": "audio", "value": self.sound85},
                86: {"type": "audio", "value": self.sound86},
                87: {"type": "audio", "value": self.sound87},
                88: {"type": "audio", "value": self.sound88},
                89: {"type": "audio", "value": self.sound89},
                90: {"type": "audio", "value": self.sound90},
                91: {"type": "audio", "value": self.sound91},
                92: {"type": "audio", "value": self.sound92},
                93: {"type": "audio", "value": self.sound93},
                94: {"type": "audio", "value": self.sound94},
                95: {"type": "audio", "value": self.sound95}
            }
        }

        self.mn8.setIcon(QIcon(r'resource\Windsong_Lyre\fQ.png'))
        self.mn8.setIconSize(QSize(80, 80))
        self.mn9.setIcon(QIcon(r'resource\Windsong_Lyre\fW.png'))
        self.mn9.setIconSize(QSize(80, 80))
        self.mn10.setIcon(QIcon(r'resource\Windsong_Lyre\fE.png'))
        self.mn10.setIconSize(QSize(80, 80))
        self.mn11.setIcon(QIcon(r'resource\Windsong_Lyre\fR.png'))
        self.mn11.setIconSize(QSize(80, 80))
        self.mn12.setIcon(QIcon(r'resource\Windsong_Lyre\fT.png'))
        self.mn12.setIconSize(QSize(80, 80))
        self.mn13.setIcon(QIcon(r'resource\Windsong_Lyre\fY.png'))
        self.mn13.setIconSize(QSize(80, 80))
        self.mn14.setIcon(QIcon(r'resource\Windsong_Lyre\fU.png'))
        self.mn14.setIconSize(QSize(80, 80))
        self.mn15.setIcon(QIcon(r'resource\Windsong_Lyre\fQ.png'))
        self.mn15.setIconSize(QSize(80, 80))
        self.mn16.setIcon(QIcon(r'resource\Windsong_Lyre\fW.png'))
        self.mn16.setIconSize(QSize(80, 80))
        self.mn17.setIcon(QIcon(r'resource\Windsong_Lyre\fE.png'))
        self.mn17.setIconSize(QSize(80, 80))
        self.mn18.setIcon(QIcon(r'resource\Windsong_Lyre\fR.png'))
        self.mn18.setIconSize(QSize(80, 80))
        self.mn19.setIcon(QIcon(r'resource\Windsong_Lyre\fT.png'))
        self.mn19.setIconSize(QSize(80, 80))
        self.mn20.setIcon(QIcon(r'resource\Windsong_Lyre\fY.png'))
        self.mn20.setIconSize(QSize(80, 80))
        self.mn21.setIcon(QIcon(r'resource\Windsong_Lyre\fU.png'))
        self.mn21.setIconSize(QSize(80, 80))
        self.mn22.setIcon(QIcon(r'resource\Windsong_Lyre\fQ.png'))
        self.mn22.setIconSize(QSize(80, 80))
        self.mn23.setIcon(QIcon(r'resource\Windsong_Lyre\fW.png'))
        self.mn23.setIconSize(QSize(80, 80))
        self.mn24.setIcon(QIcon(r'resource\Windsong_Lyre\fE.png'))
        self.mn24.setIconSize(QSize(80, 80))
        self.mn25.setIcon(QIcon(r'resource\Windsong_Lyre\fR.png'))
        self.mn25.setIconSize(QSize(80, 80))
        self.mn26.setIcon(QIcon(r'resource\Windsong_Lyre\fT.png'))
        self.mn26.setIconSize(QSize(80, 80))
        self.mn27.setIcon(QIcon(r'resource\Windsong_Lyre\fY.png'))
        self.mn27.setIconSize(QSize(80, 80))
        self.mn28.setIcon(QIcon(r'resource\Windsong_Lyre\fU.png'))
        self.mn28.setIconSize(QSize(80, 80))

        self.midi_in = rtmidi.MidiIn()
        self.current_device = None
        self.mapping_active = False
        self.active_notes = defaultdict(int)

        self.hide_yz()
        self.hide_bj()
        self.hide_jy()
        self.hide_my()
        self.hide_mn()
        self.hide_sz()
        self.refresh_midi_devices()

    def start_processing(self):
        if self.thread and self.thread.isRunning():
            self.stop_processing()
        if self.thread1 and self.thread1.isRunning():
            self.stop_processing()
        if self.thread2 and self.thread2.isRunning():
            self.stop_processing()
        
        self.file_content = None
        self.b = 0
        
        self.file_name = self.yz8.text()
        
        if not self.file_name:
            self.yz10.setText("请输入琴谱路径！")
            QTimer.singleShot(3000, self.clear_label)
            return

        if self.score_type == 'zhijian':
            self.yz1.setEnabled(False)
            self.yz2.setEnabled(True)

            try:
                with open(self.file_name, 'r', encoding='utf-8') as f:
                    self.file_content = f.read()
                    self.file_content = self.file_content.lower()
                    lines = self.file_content.splitlines(True)
            except Exception as e:
                self.yz10.setText("读取文件失败！")
                QTimer.singleShot(3000, self.clear_label)
                self.yz1.setEnabled(True)
                return

            def is_float(line):
                line = line.strip()
                if not line:
                    return False
                try:
                    float(line)
                    return True
                except ValueError:
                    return False

            def process_line(line):
                if is_float(line):
                    return line
        
                line = line.replace('+7', 'u').replace('-7', 'm')
                line = line.replace('+6', 'y').replace('-6', 'n')
                line = line.replace('+5', 't').replace('-5', 'b')
                line = line.replace('+4', 'r').replace('-4', 'v')
                line = line.replace('+3', 'e').replace('-3', 'c')
                line = line.replace('+2', 'w').replace('-2', 'x')
                line = line.replace('+1', 'q').replace('-1', 'z')
        
                line = line.replace('7', 'j')
                line = line.replace('6', 'h')
                line = line.replace('5', 'g')
                line = line.replace('4', 'f')
                line = line.replace('3', 'd')
                line = line.replace('2', 's')
                line = line.replace('1', 'a')
        
                return line

            processed_content = []
            for line in lines:
                try:
                    processed_line = process_line(line)
                    processed_content.append(processed_line)
                except Exception as e:
                    processed_content.append(line)

            self.file_content = ''.join(processed_content)

            self.thread = QThread()
            self.worker = Worker(self.file_content, self.p)
            self.worker.moveToThread(self.thread)
    
            self.thread.started.connect(self.worker.run)
            self.worker.finished.connect(self.on_worker_finished)
            self.worker.status.connect(self.handle_status)
            self.worker.finished.connect(self.worker.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)
            self.thread.finished.connect(self.on_thread_finished)
    
            self.thread.start()

        if self.score_type == 'jianzhu':
            self.yz1.setEnabled(False)
            self.yz2.setEnabled(True)

            if self.file_name[-4:] == '.txt':
                try:
                    with open(self.file_name, 'r', encoding='utf-8') as f:
                        self.file_content = f.read()
                        self.file_content = self.file_content.lower()
                except Exception as e:
                    self.yz10.setText("读取文件失败！")
                    QTimer.singleShot(3000, self.clear_label)
                    self.yz1.setEnabled(True)
                    return

            try:
                self.b = float(self.yz9.text())
                if self.b < 0:
                    self.yz10.setText("时间输入有误！")
                    QTimer.singleShot(3000, self.clear_label)
                    self.yz1.setEnabled(True)
                    return
            except ValueError:
                self.yz10.setText("时间输入有误！")
                QTimer.singleShot(3000, self.clear_label)
                self.yz1.setEnabled(True)
                return

            self.thread1 = QThread()
            self.worker1 = Worker1(self.file_content, self.b, self.file_name, self.c)
            self.worker1.moveToThread(self.thread1)

            self.thread1.started.connect(self.worker1.run)
            self.worker1.finished.connect(self.on_worker_finished1)
            self.worker1.status.connect(self.handle_status)
            self.worker1.finished.connect(self.worker1.deleteLater)
            self.thread1.finished.connect(self.thread1.deleteLater)
            self.thread1.finished.connect(self.on_thread_finished1)

            self.thread1.start()

        if self.score_type == 'guagua':
            self.yz1.setEnabled(False)
            self.yz2.setEnabled(True)

            try:
                with open(self.file_name, 'r', encoding='utf-8') as f:
                    self.file_content = f.read()
                    self.file_content = self.file_content.lower()
            except Exception as e:
                self.yz10.setText("读取文件失败！")
                QTimer.singleShot(3000, self.clear_label)
                self.yz1.setEnabled(True)
                return

            try:
                self.b = float(self.yz9.text())
                if self.b < 0:
                    self.yz10.setText("时间输入有误！")
                    QTimer.singleShot(3000, self.clear_label)
                    self.yz1.setEnabled(True)
                    return
            except ValueError:
                self.yz10.setText("时间输入有误！")
                QTimer.singleShot(3000, self.clear_label)
                self.yz1.setEnabled(True)
                return
            
            self.thread2 = QThread()
            self.worker2 = Worker2(self.file_content, self.b)
            self.worker2.moveToThread(self.thread2)
    
            self.thread2.started.connect(self.worker2.run)
            self.worker2.finished.connect(self.on_worker_finished2)
            self.worker2.status.connect(self.handle_status)
            self.worker2.finished.connect(self.worker2.deleteLater)
            self.thread2.finished.connect(self.thread2.deleteLater)
            self.thread2.finished.connect(self.on_thread_finished2)
    
            self.thread2.start()

        if self.score_type == 'midi':
            self.yz1.setEnabled(False)
            self.yz2.setEnabled(True)

            try:
                self.b = int(self.yz9.text())
                if self.b < 0:
                    self.yz10.setText("时间输入有误！")
                    QTimer.singleShot(3000, self.clear_label)
                    self.yz1.setEnabled(True)
                    return
            except ValueError:
                self.yz10.setText("时间输入有误！")
                QTimer.singleShot(3000, self.clear_label)
                self.yz1.setEnabled(True)
                return
            
            self.thread3 = QThread()
            self.worker3 = Worker3(self.b, self.file_name)
            self.worker3.moveToThread(self.thread3)
    
            self.thread3.started.connect(self.worker3.run)
            self.worker3.finished.connect(self.on_worker_finished3)
            self.worker3.status.connect(self.handle_status)
            self.worker3.finished.connect(self.worker3.deleteLater)
            self.thread3.finished.connect(self.thread3.deleteLater)
            self.thread3.finished.connect(self.on_thread_finished3)
    
            self.thread3.start()

    def stop_processing(self):
        if self.worker:
            self.worker.abort()
            if self.thread.isRunning():
                self.thread.quit()
                if not self.thread.wait(2000):
                    self.thread.terminate()
        if self.worker1:
            self.worker1.abort()
            if self.thread1.isRunning():
                self.thread1.quit()
                if not self.thread1.wait(2000):
                    self.thread1.terminate()
        if self.worker2:
            self.worker2.abort()
            if self.thread2.isRunning():
                self.thread2.quit()
                if not self.thread2.wait(2000):
                    self.thread2.terminate()
        if self.worker3:
            self.worker3.abort()
            if self.thread3.isRunning():
                self.thread3.quit()
                if not self.thread3.wait(2000):
                    self.thread3.terminate()
        
        self.yz2.setEnabled(False)
        self.yz10.setText("演奏正在停止...")
        QTimer.singleShot(3000, self.clear_label)

    def on_worker_finished(self, message):
        if message == 'completed':
            self.yz10.setText("演奏完成！")
        else:
            self.yz10.setText("演奏已停止")
        QTimer.singleShot(3000, self.clear_label)
        self.thread.quit()

    def on_worker_finished1(self, message):
        if message == 'completed':
            self.yz10.setText("演奏完成！")
        else:
            self.yz10.setText("演奏已停止")
        QTimer.singleShot(3000, self.clear_label)
        self.thread1.quit()

    def on_worker_finished2(self, message):
        if message == 'completed':
            self.yz10.setText("演奏完成！")
        else:
            self.yz10.setText("演奏已停止")
        QTimer.singleShot(3000, self.clear_label)
        self.thread2.quit()

    def on_worker_finished3(self, message):
        if message == 'completed':
            self.yz10.setText("演奏完成！")
        else:
            self.yz10.setText("演奏已停止")
        QTimer.singleShot(3000, self.clear_label)
        self.thread3.quit()

    def on_thread_finished(self):
        self.yz1.setEnabled(True)
        self.yz2.setEnabled(False)
        self.worker = None
        self.thread = None
        self.file_content = None

    def on_thread_finished1(self):
        self.yz1.setEnabled(True)
        self.yz2.setEnabled(False)
        self.worker1 = None
        self.thread1 = None
        self.file_content = None

    def on_thread_finished2(self):
        self.yz1.setEnabled(True)
        self.yz2.setEnabled(False)
        self.worker2 = None
        self.thread2 = None
        self.file_content = None

    def on_thread_finished3(self):
        self.yz1.setEnabled(True)
        self.yz2.setEnabled(False)
        self.worker3 = None
        self.thread3 = None
        self.file_content = None
        self.file_name = None

    def handle_status(self, message):
        self.yz10.setText(message)

    def closeEvent(self, event):
        if self.worker:
            self.worker.abort()
            if self.thread.isRunning():
                self.thread.quit()
                if not self.thread.wait(2000):
                    self.thread.terminate()
        if self.worker1:
            self.worker1.abort()
            if self.thread1.isRunning():
                self.thread1.quit()
                if not self.thread1.wait(2000):
                    self.thread1.terminate()
        if self.worker2:
            self.worker2.abort()
            if self.thread2.isRunning():
                self.thread2.quit()
                if not self.thread2.wait(2000):
                    self.thread2.terminate()
        if self.worker3:
            self.worker3.abort()
            if self.thread3.isRunning():
                self.thread3.quit()
                if not self.thread3.wait(2000):
                    self.thread3.terminate()
        try:
            keyboard.unhook_all()
        except:
            pass
        self.stop_midi_mapping()
        self.stop_mn_mapping()
        self.stop_playback()
        pygame.mixer.quit()
        event.accept()

    def clear_label(self):
        self.yz10.clear()

    def hide_yz(self):
        self.yz1.setHidden(True)
        self.yz2.setHidden(True)
        self.yz3.setHidden(True)
        self.yz4.setHidden(True)
        self.yz5.setHidden(True)
        self.yz6.setHidden(True)
        self.yz7.setHidden(True)
        self.yz8.setHidden(True)
        self.yz9.setHidden(True)
        self.yz10.setHidden(True)
        self.yz11.setHidden(True)

    def hide_bj(self):
        self.yz1.setHidden(True)
        self.yz2.setHidden(True)
        self.yz3.setHidden(True)
        self.yz4.setHidden(True)
        self.yz5.setHidden(True)
        self.yz6.setHidden(True)
        self.yz7.setHidden(True)
        self.yz8.setHidden(True)
        self.yz9.setHidden(True)
        self.yz10.setHidden(True)
        self.yz11.setHidden(True)
        self.bj1.setHidden(True)
        self.bj2.setHidden(True)
        self.bj3.setHidden(True)
        self.bj4.setHidden(True)
        self.bj5.setHidden(True)
        self.bj6.setHidden(True)
        self.bj7.setHidden(True)
        self.bj8.setHidden(True)
        self.bj9.setHidden(True)
        self.bj10.setHidden(True)
        self.bj11.setHidden(True)
        self.bj12.setHidden(True)
        self.bj13.setHidden(True)
        self.bj14.setHidden(True)
        self.bj15.setHidden(True)
        self.bj16.setHidden(True)
        self.bj17.setHidden(True)
        self.bj18.setHidden(True)
        self.bj19.setHidden(True)
        self.bj20.setHidden(True)
        self.bj21.setHidden(True)
        self.bj22.setHidden(True)
        self.bj23.setHidden(True)
        self.bj24.setHidden(True)
        self.bj25.setHidden(True)
        self.bj26.setHidden(True)
        self.bj27.setHidden(True)
        self.bj28.setHidden(True)
        self.bj29.setHidden(True)
        self.bj30.setHidden(True)
        self.bj31.setHidden(True)
        self.bj32.setHidden(True)
        self.bj33.setHidden(True)
        self.bj34.setHidden(True)
        self.bj35.setHidden(True)
        self.bj36.setHidden(True)
        self.bj37.setHidden(True)
        self.bj38.setHidden(True)
        self.bj39.setHidden(True)
        self.bj40.setHidden(True)
        self.bj41.setHidden(True)
        self.bj42.setHidden(True)
        self.bj43.setHidden(True)
        self.bj44.setHidden(True)
        self.bj45.setHidden(True)
        self.bj46.setHidden(True)
        self.bj47.setHidden(True)
        self.bj48.setHidden(True)
        self.bj49.setHidden(True)
        self.bj50.setHidden(True)
        self.bj51.setHidden(True)

    def hide_jy(self):
        self.jy1.setHidden(True)
        self.jy2.setHidden(True)
        self.jy3.setHidden(True)
        self.jy4.setHidden(True)
        self.jy5.setHidden(True)
        self.jy6.setHidden(True)
        self.jy7.setHidden(True)

    def hide_my(self):
        self.my1.setHidden(True)
        self.my2.setHidden(True)
        self.my3.setHidden(True)
        self.my4.setHidden(True)
        self.my5.setHidden(True)
        self.my6.setHidden(True)
        self.my7.setHidden(True)
        self.my8.setHidden(True)

    def hide_mn(self):
        self.mn1.setHidden(True)
        self.mn2.setHidden(True)
        self.mn3.setHidden(True)
        self.mn4.setHidden(True)
        self.mn5.setHidden(True)
        self.mn6.setHidden(True)
        self.mn7.setHidden(True)
        self.mn8.setHidden(True)
        self.mn9.setHidden(True)
        self.mn10.setHidden(True)
        self.mn11.setHidden(True)
        self.mn12.setHidden(True)
        self.mn13.setHidden(True)
        self.mn14.setHidden(True)
        self.mn15.setHidden(True)
        self.mn16.setHidden(True)
        self.mn17.setHidden(True)
        self.mn18.setHidden(True)
        self.mn19.setHidden(True)
        self.mn20.setHidden(True)
        self.mn21.setHidden(True)
        self.mn22.setHidden(True)
        self.mn23.setHidden(True)
        self.mn24.setHidden(True)
        self.mn25.setHidden(True)
        self.mn26.setHidden(True)
        self.mn27.setHidden(True)
        self.mn28.setHidden(True)
        self.mn29.setHidden(True)
        self.mn30.setHidden(True)
        self.mn31.setHidden(True)
        self.mn32.setHidden(True)
        self.mn33.setHidden(True)
        self.mn34.setHidden(True)
        self.mn35.setHidden(True)
        self.mn36.setHidden(True)
        self.mn37.setHidden(True)
        self.mn38.setHidden(True)
        self.mn39.setHidden(True)
        self.mn40.setHidden(True)
        self.mn41.setHidden(True)
        self.mn42.setHidden(True)
        self.mn43.setHidden(True)
        self.mn44.setHidden(True)
        self.mn45.setHidden(True)
        self.mn46.setHidden(True)
        self.mn47.setHidden(True)
        self.mn48.setHidden(True)
        self.mn49.setHidden(True)
        self.mn50.setHidden(True)
        self.mn51.setHidden(True)
        self.mn52.setHidden(True)
        self.mn53.setHidden(True)
        self.mn54.setHidden(True)
        self.mn55.setHidden(True)
        self.mn56.setHidden(True)
        self.mn57.setHidden(True)
        self.mn58.setHidden(True)
        self.mn59.setHidden(True)
        self.mn60.setHidden(True)
        self.mn61.setHidden(True)
        self.mn62.setHidden(True)
        self.mn63.setHidden(True)
        self.mn64.setHidden(True)
        self.mn65.setHidden(True)
        self.mn66.setHidden(True)
        self.mn67.setHidden(True)
        self.mn68.setHidden(True)
        self.mn69.setHidden(True)
        self.mn70.setHidden(True)
        self.mn71.setHidden(True)
        self.mn72.setHidden(True)
        self.mn73.setHidden(True)
        self.mn74.setHidden(True)
        self.mn75.setHidden(True)
        self.mn76.setHidden(True)
        self.mn77.setHidden(True)
        self.mn78.setHidden(True)
        self.mn79.setHidden(True)
        self.mn80.setHidden(True)
        self.mn81.setHidden(True)
        self.mn82.setHidden(True)
        self.mn83.setHidden(True)
        self.mn84.setHidden(True)
        self.mn85.setHidden(True)
        self.mn86.setHidden(True)
        self.mn87.setHidden(True)
        self.mn88.setHidden(True)

    def hide_sz(self):
        self.sz1.setHidden(True)
        self.sz2.setHidden(True)
        self.sz3.setHidden(True)
        self.sz4.setHidden(True)
        self.sz5.setHidden(True)
        self.sz6.setHidden(True)
        self.sz7.setHidden(True)
        self.sz8.setHidden(True)
        self.sz9.setHidden(True)
        self.sz10.setHidden(True)
        self.sz11.setHidden(True)

    def hide_sy(self):
        self.sy1.setHidden(True)
        self.sy2.setHidden(True)
        self.sy3.setHidden(True)

    def yz3p(self):
        size = pyautogui.size()
        size0 = str(size)
        if size0 == 'Size(width=1440, height=900)':
            self.yz10.setText("屏幕分辨率正常！")
            QTimer.singleShot(3000, self.clear_label)
        else:
            self.yz10.setText("请调节屏幕分辨率至1440,900（如需使用模拟鼠标谱）！")
            QTimer.singleShot(3000, self.clear_label)

    def yz4p(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "所有文件 (*);;文本文档 (*.txt)", options=options)
        self.yz8.setText(file_path)

    def yz11p(self, index):
        if index == 0:
            self.score_type = 'jianzhu'
            self.yz6.setText('输入音距(建筑谱)')
            self.yz7.setText('(支持浮点数、整数，单位s)')
        elif index == 1:
            self.score_type = 'zhijian'
        elif index == 2:
            self.score_type = 'guagua'
            self.yz6.setText('输入按键速度(呱呱谱)')
            self.yz7.setText('(支持浮点数、整数，单位ms)')
        elif index == 3:
            self.score_type = 'midi'
            self.yz6.setText('输入BPM(MIDI谱)')
            self.yz7.setText('(仅整数，单位beats/min)')

    def dh1p(self):
        self.Label1.setText('《原琴辅助演奏4.0-winx64》，在旅途')
        self.mn_listener = 0
        self.hide_yz()
        self.hide_bj()
        self.hide_jy()
        self.hide_my()
        self.hide_mn()
        self.hide_sz()
        self.sy1.setHidden(False)
        self.sy2.setHidden(False)
        self.sy3.setHidden(False)

    def dh2p(self):
        self.Label1.setText('自动演奏')
        self.mn_listener = 0
        self.hide_sy()
        self.hide_bj()
        self.hide_jy()
        self.hide_my()
        self.hide_mn()
        self.hide_sz()
        self.yz1.setHidden(False)
        self.yz2.setHidden(False)
        self.yz3.setHidden(False)
        self.yz4.setHidden(False)
        self.yz5.setHidden(False)
        self.yz6.setHidden(False)
        self.yz7.setHidden(False)
        self.yz8.setHidden(False)
        self.yz9.setHidden(False)
        self.yz10.setHidden(False)
        self.yz11.setHidden(False)

    def dh3p(self):
        self.Label1.setText('曲谱编辑')
        self.mn_listener = 0
        self.hide_sy()
        self.hide_yz()
        self.hide_bj()
        self.hide_jy()
        self.hide_my()
        self.hide_mn()
        self.hide_sz()
        self.bj1.setHidden(False)
        self.bj2.setHidden(False)
        self.bj3.setHidden(False)
        self.bj4.setHidden(False)
        self.bj5.setHidden(False)
        self.bj6.setHidden(False)
        self.bj7.setHidden(False)
        self.bj8.setHidden(False)
        self.bj9.setHidden(False)
        self.bj10.setHidden(False)
        self.bj11.setHidden(False)
        self.bj12.setHidden(False)
        self.bj13.setHidden(False)
        self.bj14.setHidden(False)
        self.bj15.setHidden(False)
        self.bj16.setHidden(False)
        self.bj17.setHidden(False)
        self.bj18.setHidden(False)
        self.bj19.setHidden(False)
        self.bj20.setHidden(False)
        self.bj21.setHidden(False)
        self.bj22.setHidden(False)
        self.bj23.setHidden(False)
        self.bj24.setHidden(False)
        self.bj25.setHidden(False)
        self.bj26.setHidden(False)
        self.bj27.setHidden(False)
        self.bj28.setHidden(False)
        self.bj29.setHidden(False)
        self.bj30.setHidden(False)
        self.bj31.setHidden(False)
        self.bj32.setHidden(False)
        self.bj33.setHidden(False)
        self.bj34.setHidden(False)
        self.bj35.setHidden(False)
        self.bj36.setHidden(False)
        self.bj37.setHidden(False)
        self.bj38.setHidden(False)
        self.bj39.setHidden(False)
        self.bj45.setHidden(False)
        self.bj46.setHidden(False)
        self.bj47.setHidden(False)
        self.bj48.setHidden(False)
        self.bj51.setHidden(False)
        
    def dh4p(self):
        self.Label1.setText('键盘映射')
        self.mn_listener = 0
        self.hide_sy()
        self.hide_bj()
        self.hide_yz()
        self.hide_my()
        self.hide_mn()
        self.hide_sz()
        self.jy1.setHidden(False)
        self.jy2.setHidden(False)
        self.jy3.setHidden(False)
        self.jy4.setHidden(False)
        self.jy5.setHidden(False)
        self.jy6.setHidden(False)
        self.jy7.setHidden(False)

    def dh5p(self):
        self.Label1.setText('MIDI映射')
        self.stop_mn_mapping()
        self.mn_listener = 0
        self.hide_sy()
        self.hide_bj()
        self.hide_yz()
        self.hide_jy()
        self.hide_mn()
        self.hide_sz()
        self.my1.setHidden(False)
        self.my2.setHidden(False)
        self.my3.setHidden(False)
        self.my4.setHidden(False)
        self.my5.setHidden(False)
        self.my6.setHidden(False)
        self.my7.setHidden(False)
        self.my8.setHidden(False)

    def dh6p(self):
        self.Label1.setText('模拟原琴')
        self.stop_midi_mapping()
        self.mn75.setCurrentIndex(0)
        self.mn_listener = 1
        self.hide_sy()
        self.hide_yz()
        self.hide_bj()
        self.hide_jy()
        self.hide_my()
        self.hide_mn()
        self.hide_sz()
        self.mn1.setHidden(False)
        self.mn2.setHidden(False)
        self.mn3.setHidden(False)
        self.mn4.setHidden(False)
        self.mn5.setHidden(False)
        self.mn6.setHidden(False)
        self.mn7.setHidden(False)
        self.mn8.setHidden(False)
        self.mn9.setHidden(False)
        self.mn10.setHidden(False)
        self.mn11.setHidden(False)
        self.mn12.setHidden(False)
        self.mn13.setHidden(False)
        self.mn14.setHidden(False)
        self.mn15.setHidden(False)
        self.mn16.setHidden(False)
        self.mn17.setHidden(False)
        self.mn18.setHidden(False)
        self.mn19.setHidden(False)
        self.mn20.setHidden(False)
        self.mn21.setHidden(False)
        self.mn22.setHidden(False)
        self.mn23.setHidden(False)
        self.mn24.setHidden(False)
        self.mn25.setHidden(False)
        self.mn26.setHidden(False)
        self.mn27.setHidden(False)
        self.mn28.setHidden(False)
        self.mn29.setHidden(False)
        self.mn30.setHidden(False)
        self.mn31.setHidden(False)
        self.mn32.setHidden(False)
        self.mn33.setHidden(False)
        self.mn34.setHidden(False)
        self.mn35.setHidden(False)
        self.mn36.setHidden(False)
        self.mn37.setHidden(False)
        self.mn38.setHidden(False)
        self.mn39.setHidden(False)
        self.mn40.setHidden(False)
        self.mn41.setHidden(False)
        self.mn42.setHidden(False)
        self.mn43.setHidden(False)
        self.mn44.setHidden(False)
        self.mn45.setHidden(False)
        self.mn46.setHidden(False)
        self.mn47.setHidden(False)
        self.mn48.setHidden(False)
        self.mn49.setHidden(False)
        self.mn50.setHidden(False)
        self.mn51.setHidden(False)
        self.mn52.setHidden(False)
        self.mn53.setHidden(False)
        self.mn54.setHidden(False)
        self.mn55.setHidden(False)
        self.mn56.setHidden(False)
        self.mn57.setHidden(False)
        self.mn58.setHidden(False)
        self.mn59.setHidden(False)
        self.mn60.setHidden(False)
        self.mn75.setHidden(False)
        self.mn76.setHidden(False)
        self.mn77.setHidden(False)
        self.mn78.setHidden(False)
        self.mn79.setHidden(False)
        self.mn80.setHidden(False)
        self.mn81.setHidden(False)
        self.mn82.setHidden(False)
        self.mn83.setHidden(False)
        self.mn84.setHidden(False)
        self.mn85.setHidden(False)
        self.mn86.setHidden(False)
        self.mn87.setHidden(False)
        self.mn88.setHidden(False)

    def dh7p(self):
        self.Label1.setText('设置')
        self.mn_listener = 0
        self.hide_sy()
        self.hide_yz()
        self.hide_bj()
        self.hide_jy()
        self.hide_my()
        self.hide_mn()
        self.sz1.setHidden(False)
        self.sz2.setHidden(False)
        self.sz3.setHidden(False)
        self.sz4.setHidden(False)
        self.sz5.setHidden(False)
        self.sz6.setHidden(False)
        self.sz7.setHidden(False)
        self.sz8.setHidden(False)
        self.sz9.setHidden(False)
        self.sz10.setHidden(False)
        self.sz11.setHidden(False)

    def bj1p(self, file_path):

        compounded_string, file_name1 = self.bjcl()

        if not file_name1:
            self.bj51.setText("请输入琴谱路径！")
            QTimer.singleShot(3000, self.clear_label1)
        else:
            self.bj1.setEnabled(False)
            self.bj2.setEnabled(False)
            self.bj37.setEnabled(False)
            with open(file_name1, 'a', encoding='utf-8') as file:
                file.writelines('\n' + compounded_string)

            self.bj51.setText("编辑已完成！")
            QTimer.singleShot(3000, self.clear_label1)

    def bj2p(self):

        compounded_string, file_name1 = self.bjcl()
        
        appointed_line_number = int(self.bj35.text()) if self.bj35.text() else 0
        if not file_name1:
            self.bj51.setText("请输入琴谱路径！")
            QTimer.singleShot(3000, self.clear_label1)
        else:
            with open(file_name1, 'r', encoding='utf-8') as file:
                file_lines = file.readlines()
            if 1 <= appointed_line_number <= len(file_lines):
                file_lines[appointed_line_number - 1] = compounded_string + '\n'

                self.bj1.setEnabled(False)
                self.bj2.setEnabled(False)
                self.bj37.setEnabled(False)
                
                with open(file_name1, 'w', encoding='utf-8') as file:
                    file.writelines(file_lines)

                self.bj51.setText("编辑已完成！")
                QTimer.singleShot(3000, self.clear_label1)
                
            else:
                self.bj51.setText(f"行号 {appointed_line_number} 无效，文件只有 {len(file_lines)} 行。")
                QTimer.singleShot(3000, self.clear_label1)
                
    def bj37p(self):

        compounded_string, file_name1 = self.bjcl()

        appointed_line_number = int(self.bj35.text()) if self.bj35.text() else 0

        if not file_name1:
            self.bj51.setText("请输入琴谱路径！")
            QTimer.singleShot(3000, self.clear_label1)
        else:
            with open(file_name1, 'r', encoding='utf-8') as file:
                file_lines = file.readlines()
            if 1 <= appointed_line_number <= len(file_lines):
                file_lines[appointed_line_number - 1] = file_lines[appointed_line_number - 1].rstrip('\n') + compounded_string + '\n'

                self.bj1.setEnabled(False)
                self.bj2.setEnabled(False)
                self.bj37.setEnabled(False)
                
                with open(file_name1, 'w', encoding='utf-8') as file:
                    file.writelines(file_lines)

                self.bj51.setText("编辑已完成！")
                QTimer.singleShot(3000, self.clear_label1)
                
            else:
                self.bj51.setText(f"行号 {appointed_line_number} 无效，文件只有 {len(file_lines)} 行。")
                QTimer.singleShot(3000, self.clear_label1)

    def bj42p(self):
        replace_rule1 = self.bj49.toPlainText()
        replace_rule2 = self.bj50.toPlainText()
        string_to_replace = self.bj40.toPlainText()
        
        new_string = string_to_replace.replace(replace_rule1, replace_rule2)
        self.bj41.setText(new_string)

    def bj44p(self):
        self.bj40.clear()
        self.bj41.clear()
        self.bj49.clear()
        self.bj50.clear()

    def bj45p(self):
        self.bj3.clear()
        self.bj4.clear()
        self.bj5.clear()
        self.bj6.clear()
        self.bj7.clear()
        self.bj8.clear()
        self.bj9.clear()
        self.bj10.clear()
        self.bj11.clear()
        self.bj12.clear()
        self.bj13.clear()
        self.bj14.clear()
        self.bj15.clear()
        self.bj16.clear()
        self.bj17.clear()
        self.bj18.clear()
        self.bj19.clear()
        self.bj20.clear()
        self.bj21.clear()
        self.bj22.clear()
        self.bj23.clear()
        self.bj24.clear()
        self.bj25.clear()
        self.bj26.clear()
        self.bj27.clear()
        self.bj28.clear()
        self.bj29.clear()
        self.bj30.clear()
        self.bj31.clear()
        self.bj32.clear()
        self.bj33.clear()
        self.bj34.clear()

    def bj38p(self):
        self.bj40.setHidden(True)
        self.bj41.setHidden(True)
        self.bj42.setHidden(True)
        self.bj43.setHidden(True)
        self.bj44.setHidden(True)
        self.bj49.setHidden(True)
        self.bj50.setHidden(True)
        self.bj1.setHidden(False)
        self.bj2.setHidden(False)
        self.bj3.setHidden(False)
        self.bj4.setHidden(False)
        self.bj5.setHidden(False)
        self.bj6.setHidden(False)
        self.bj7.setHidden(False)
        self.bj8.setHidden(False)
        self.bj9.setHidden(False)
        self.bj10.setHidden(False)
        self.bj11.setHidden(False)
        self.bj12.setHidden(False)
        self.bj13.setHidden(False)
        self.bj14.setHidden(False)
        self.bj15.setHidden(False)
        self.bj16.setHidden(False)
        self.bj17.setHidden(False)
        self.bj18.setHidden(False)
        self.bj19.setHidden(False)
        self.bj20.setHidden(False)
        self.bj21.setHidden(False)
        self.bj22.setHidden(False)
        self.bj23.setHidden(False)
        self.bj24.setHidden(False)
        self.bj25.setHidden(False)
        self.bj26.setHidden(False)
        self.bj27.setHidden(False)
        self.bj28.setHidden(False)
        self.bj29.setHidden(False)
        self.bj30.setHidden(False)
        self.bj31.setHidden(False)
        self.bj32.setHidden(False)
        self.bj33.setHidden(False)
        self.bj34.setHidden(False)
        self.bj35.setHidden(False)
        self.bj36.setHidden(False)
        self.bj37.setHidden(False)
        self.bj45.setHidden(False)
        self.bj46.setHidden(False)
        self.bj47.setHidden(False)
        self.bj48.setHidden(False)
        self.bj51.setHidden(False)

    def bj39p(self):
        self.bj40.setHidden(False)
        self.bj41.setHidden(False)
        self.bj42.setHidden(False)
        self.bj43.setHidden(False)
        self.bj44.setHidden(False)
        self.bj49.setHidden(False)
        self.bj50.setHidden(False)
        self.bj1.setHidden(True)
        self.bj2.setHidden(True)
        self.bj3.setHidden(True)
        self.bj4.setHidden(True)
        self.bj5.setHidden(True)
        self.bj6.setHidden(True)
        self.bj7.setHidden(True)
        self.bj8.setHidden(True)
        self.bj9.setHidden(True)
        self.bj10.setHidden(True)
        self.bj11.setHidden(True)
        self.bj12.setHidden(True)
        self.bj13.setHidden(True)
        self.bj14.setHidden(True)
        self.bj15.setHidden(True)
        self.bj16.setHidden(True)
        self.bj17.setHidden(True)
        self.bj18.setHidden(True)
        self.bj19.setHidden(True)
        self.bj20.setHidden(True)
        self.bj21.setHidden(True)
        self.bj22.setHidden(True)
        self.bj23.setHidden(True)
        self.bj24.setHidden(True)
        self.bj25.setHidden(True)
        self.bj26.setHidden(True)
        self.bj27.setHidden(True)
        self.bj28.setHidden(True)
        self.bj29.setHidden(True)
        self.bj30.setHidden(True)
        self.bj31.setHidden(True)
        self.bj32.setHidden(True)
        self.bj33.setHidden(True)
        self.bj34.setHidden(True)
        self.bj35.setHidden(True)
        self.bj36.setHidden(True)
        self.bj37.setHidden(True)
        self.bj45.setHidden(True)
        self.bj46.setHidden(True)
        self.bj47.setHidden(True)
        self.bj48.setHidden(True)
        self.bj51.setHidden(True)

    def bj46p(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "所有文件 (*);;文本文档 (*.txt)", options=options)
        self.bj47.setText(file_path)
        return file_path

    def bjcl(self):
        pj1 = self.bj3.text()
        pj2 = self.bj4.text()
        pj3 = self.bj5.text()
        pj4 = self.bj6.text()
        pj5 = self.bj7.text()
        pj6 = self.bj8.text()
        pj7 = self.bj9.text()
        pj8 = self.bj10.text()
        pj9 = self.bj11.text()
        pj10 = self.bj12.text()
        pj11 = self.bj13.text()
        pj12 = self.bj14.text()
        pj13 = self.bj15.text()
        pj14 = self.bj16.text()
        pj15 = self.bj17.text()
        pj16 = self.bj18.text()
        pj17 = self.bj19.text()
        pj18 = self.bj20.text()
        pj19 = self.bj21.text()
        pj20 = self.bj22.text()
        pj21 = self.bj23.text()
        pj22 = self.bj24.text()
        pj23 = self.bj25.text()
        pj24 = self.bj26.text()
        pj25 = self.bj27.text()
        pj26 = self.bj28.text()
        pj27 = self.bj29.text()
        pj28 = self.bj30.text()
        pj29 = self.bj31.text()
        pj30 = self.bj32.text()
        pj31 = self.bj33.text()
        pj32 = self.bj34.text()

        if len(pj1) < 2:
            pj1 = pj1.ljust(2, '0')
        else:
            pj1 = pj1[:2]
        if len(pj2) < 2:
            pj2 = pj2.ljust(2, '0')
        else:
            pj2 = pj2[:2]
        if len(pj3) < 2:
            pj3 = pj3.ljust(2, '0')
        else:
            pj3 = pj3[:2]
        if len(pj4) < 2:
            pj4 = pj4.ljust(2, '0')
        else:
            pj4 = pj4[:2]
        if len(pj5) < 2:
            pj5 = pj5.ljust(2, '0')
        else:
            pj5 = pj5[:2]
        if len(pj6) < 2:
            pj6 = pj6.ljust(2, '0')
        else:
            pj6 = pj6[:2]
        if len(pj7) < 2:
            pj7 = pj7.ljust(2, '0')
        else:
            pj7 = pj7[:2]
        if len(pj8) < 2:
            pj8 = pj8.ljust(2, '0')
        else:
            pj8 = pj8[:2]
        if len(pj9) < 2:
            pj9 = pj9.ljust(2, '0')
        else:
            pj9 = pj9[:2]
        if len(pj10) < 2:
            pj10 = pj10.ljust(2, '0')
        else:
            pj10 = pj10[:2]
        if len(pj11) < 2:
            pj11 = pj11.ljust(2, '0')
        else:
            pj11 = pj11[:2]
        if len(pj12) < 2:
            pj12 = pj12.ljust(2, '0')
        else:
            pj12 = pj12[:2]
        if len(pj13) < 2:
            pj13 = pj13.ljust(2, '0')
        else:
            pj13 = pj13[:2]
        if len(pj14) < 2:
            pj14 = pj14.ljust(2, '0')
        else:
            pj14 = pj14[:2]
        if len(pj15) < 2:
            pj15 = pj15.ljust(2, '0')
        else:
            pj15 = pj15[:2]
        if len(pj16) < 2:
            pj16 = pj16.ljust(2, '0')
        else:
            pj16 = pj16[:2]
        if len(pj17) < 2:
            pj17 = pj17.ljust(2, '0')
        else:
            pj17 = pj17[:2]
        if len(pj18) < 2:
            pj18 = pj18.ljust(2, '0')
        else:
            pj18 = pj18[:2]
        if len(pj19) < 2:
            pj19 = pj19.ljust(2, '0')
        else:
            pj19 = pj19[:2]
        if len(pj20) < 2:
            pj20 = pj20.ljust(2, '0')
        else:
            pj20 = pj20[:2]
        if len(pj21) < 2:
            pj21 = pj21.ljust(2, '0')
        else:
            pj21 = pj21[:2]
        if len(pj22) < 2:
            pj22 = pj22.ljust(2, '0')
        else:
            pj22 = pj22[:2]
        if len(pj23) < 2:
            pj23 = pj23.ljust(2, '0')
        else:
            pj23 = pj23[:2]
        if len(pj24) < 2:
            pj24 = pj24.ljust(2, '0')
        else:
            pj24 = pj24[:2]
        if len(pj25) < 2:
            pj25 = pj25.ljust(2, '0')
        else:
            pj25 = pj25[:2]
        if len(pj26) < 2:
            pj26 = pj26.ljust(2, '0')
        else:
            pj26 = pj26[:2]
        if len(pj27) < 2:
            pj27 = pj27.ljust(2, '0')
        else:
            pj27 = pj27[:2]
        if len(pj28) < 2:
            pj28 = pj28.ljust(2, '0')
        else:
            pj28 = pj28[:2]
        if len(pj29) < 2:
            pj29 = pj29.ljust(2, '0')
        else:
            pj29 = pj29[:2]
        if len(pj30) < 2:
            pj30 = pj30.ljust(2, '0')
        else:
            pj30 = pj30[:2]
        if len(pj31) < 2:
            pj31 = pj31.ljust(2, '0')
        else:
            pj31 = pj31[:2]
        if len(pj32) < 2:
            pj32 = pj32.ljust(2, '0')
        else:
            pj32 = pj32[:2]

        compounded_string = pj1+pj17+'/'+pj2+pj18+'/'+pj3+pj19+'/'+pj4+pj20+'/'+pj5+pj21+'/'+pj6+pj22+'/'+pj7+pj23+'/'+pj8+pj24+'/'+pj9+pj25+'/'+pj10+pj26+'/'+pj11+pj27+'/'+pj12+pj28+'/'+pj13+pj29+'/'+pj14+pj30+'/'+pj15+pj31+'/'+pj16+pj32+'/'
        file_name1 = self.bj47.text()
        return compounded_string, file_name1

    def clear_label1(self):
        self.bj51.clear()
        self.bj1.setEnabled(True)
        self.bj2.setEnabled(True)
        self.bj37.setEnabled(True)

    def clear_label2(self):
        self.jy6.clear()

    def map_keys(self):

        self.input_key = self.jy2.currentText().split(":")[1] if ":" in self.jy2.currentText() else self.jy2.currentText()
        self.output_key = self.jy3.currentText().split(":")[1] if ":" in self.jy3.currentText() else self.jy3.currentText()

        if not self.input_key or not self.output_key:
            self.jy6.setText("请输入原键和目标键！")
            QTimer.singleShot(3000, self.clear_label2)
            return

        try:
            keyboard.remap_key(self.input_key, self.output_key)
            self.jy6.setText(f'已映射 {self.input_key} -> {self.output_key}')
            QTimer.singleShot(3000, self.clear_label2)
        except Exception as e:
            self.jy6.setText('映射失败！')
            QTimer.singleShot(3000, self.clear_label2)

    def unmap_keys(self):

        self.input_key = self.jy2.currentText().split(":")[1] if ":" in self.jy2.currentText() else self.jy2.currentText()
        self.output_key = self.jy3.currentText().split(":")[1] if ":" in self.jy3.currentText() else self.jy3.currentText()

        if not self.input_key:
            self.jy6.setText("请输入原键和目标键！")
            QTimer.singleShot(3000, self.clear_label2)
            return

        try:
            keyboard.unremap_key(self.input_key)
            self.jy6.setText(f'已取消映射 {self.input_key}')
            QTimer.singleShot(3000, self.clear_label2)
        except Exception as e:
            self.jy6.setText('取消映射失败！')
            QTimer.singleShot(3000, self.clear_label2)

    def unmap_all_keys(self):

        try:
            possible_keys = [
                *[chr(i) for i in range(ord('a'), ord('z') + 1)],
                *[chr(i) for i in range(ord('0'), ord('9') + 1)],
                *['f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12'],
                'space', 'enter', 'esc', 'tab', 'backspace', 'shift', 'ctrl', 'alt',
                'up', 'down', 'left', 'right', 'insert', 'delete', 'home', 'end', 'pageup', 'pagedown',
            ]
            
            for key in possible_keys:
                try:
                    keyboard.unremap_key(key)
                except:
                    pass
            
            self.jy6.setText('已取消所有映射！')
            QTimer.singleShot(3000, self.clear_label2)
        except Exception as e:
            self.jy6.setText('取消所有映射失败！')
            QTimer.singleShot(3000, self.clear_label2)

    def jy2p(self):
        selected_text = self.jy2.currentText()
        self.input_key = selected_text.replace("原键:", "")

    def jy3p(self):
        selected_text = self.jy3.currentText()
        self.output_key = selected_text.replace("目标键:", "")

    def refresh_midi_devices(self):
        self.my1.clear()
        self.mn76.clear()
        ports = self.midi_in.get_ports()
        
        if not ports:
            self.my1.addItem('未找到MIDI设备', None)
            self.mn76.addItem('未找到MIDI设备', None)
        else:
            for i, port in enumerate(ports):
                self.my1.addItem(port, i)
                self.mn76.addItem(port, i)

    def start_midi_mapping(self):
        """开始MIDI映射"""
        if self.current_device is not None:
            self.midi_in.close_port()
        
        device_index = self.my1.currentData()
        if device_index is None:
            self.my8.setText("错误，请选择有效的MIDI设备！")
            QTimer.singleShot(3000, self.clear_label3)
            return
        
        preset_name = self.my3.currentText()
        if preset_name not in self.presets:
            self.my8.setText("错误，无效的映射方案！")
            QTimer.singleShot(3000, self.clear_label3)
            return
        
        self.current_mapping = self.presets[preset_name]
        
        try:
            self.midi_in.open_port(device_index)
            self.midi_in.set_callback(self.midi_callback)
            self.current_device = device_index
            self.mapping_active = True
            
            self.my5.setEnabled(False)
            self.my6.setEnabled(True)
            device_name = self.my1.currentText()
            
        except Exception as e:
            self.stop_midi_mapping()
            self.my8.setText("连接错误，无法打开MIDI设备！")
            QTimer.singleShot(3000, self.clear_label3)

    def stop_midi_mapping(self):
        """停止MIDI映射"""
        
        if not hasattr(self, 'mapping_active') or not self.mapping_active:
            return
        
        try:
            if hasattr(self, 'midi_in') and self.midi_in:
                self.midi_in.close_port()
            
            if hasattr(self, 'active_notes'):
                self.active_notes.clear()
                
            if hasattr(self, 'current_mapping'):
                for note, mapping in self.current_mapping.items():
                    if mapping["type"] == "key":
                        try:
                            keyboard.release(mapping["value"])
                        except:
                            pass
            
            self.mapping_active = False
            if hasattr(self, 'current_device'):
                self.current_device = None
        except:
            pass
        
        if hasattr(self, 'my5') and hasattr(self, 'my6'):
            self.my5.setEnabled(True)
            self.my6.setEnabled(False)

        self.my5.setEnabled(True)
        self.my6.setEnabled(False)

    def midi_callback(self, event, data=None):
        """MIDI输入回调函数"""
        message, delta_time = event
        
        if len(message) < 3:
            return
    
        status = message[0] & 0xF0
        note = message[1]
        velocity = message[2]
    
        if status == 0x90 and velocity > 0:
            self.handle_note_on(note)
        elif status == 0x80 or (status == 0x90 and velocity == 0):
            self.handle_note_off(note)

    def handle_note_on(self, note):
        """处理音符按下事件"""
        if note in self.current_mapping:
            mapping = self.current_mapping[note]
        
            audio = mapping.get("audio") if "audio" in mapping else mapping["value"] if mapping.get("type") == "audio" else None
            if audio and hasattr(audio, 'play'):
                try:
                    audio.play()
                except Exception as e:
                    self.my8.setText("播放音频失败！")
                    QTimer.singleShot(3000, self.clear_label3)
        
            if mapping.get("type") == "key" and isinstance(mapping["value"], str):
                key = mapping["value"]
                self.active_notes[note] += 1
                if self.active_notes[note] == 1:
                    try:
                        keyboard.press(key)
                    except Exception as e:
                        self.my8.setText("按键按下失败！")
                        QTimer.singleShot(3000, self.clear_label3)
    
    def handle_note_off(self, note):
        """处理音符释放事件"""
        if note in self.current_mapping:
            mapping = self.current_mapping[note]
            
            if mapping["type"] == "key" and isinstance(mapping["value"], str):
                key = mapping["value"]
                if note in self.active_notes:
                    self.active_notes[note] -= 1
                
                    if self.active_notes[note] <= 0:
                        del self.active_notes[note]
                        try:
                            keyboard.release(key)
                        except Exception as e:
                            self.jy6.setText("按键释放失败！")
                            QTimer.singleShot(3000, self.clear_label3)

    def clear_label3(self):
        self.my8.clear()

    def my3p(self, index):
        if 0 <= index <= 4:
            try:
                self.sound36 = pygame.mixer.Sound(r'resource\Windsong_Lyre\,.wav')
                self.sound37 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#,.wav')
                self.sound38 = pygame.mixer.Sound(r'resource\Windsong_Lyre\..wav')
                self.sound39 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#..wav')
                self.sound40 = pygame.mixer.Sound(r'resource\Windsong_Lyre\xie.wav')
                self.sound41 = pygame.mixer.Sound(r'resource\Windsong_Lyre\;.wav')
                self.sound42 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#;.wav')
                self.sound43 = pygame.mixer.Sound(r'resource\Windsong_Lyre\'.wav')
                self.sound44 = pygame.mixer.Sound('resource\\Windsong_Lyre\\#\'.wav')
                self.sound45 = pygame.mixer.Sound(r'resource\Windsong_Lyre\[.wav')
                self.sound46 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#[.wav')
                self.sound47 = pygame.mixer.Sound(r'resource\Windsong_Lyre\].wav')
                self.sound49 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Z.wav')
                self.sound51 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#X.wav')
                self.sound52 = None
                self.sound53 = None
                self.sound54 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#V.wav')
                self.sound55 = None
                self.sound56 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#B.wav')
                self.sound57 = None
                self.sound58 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#N.wav')
                self.sound59 = None
                self.sound61 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#A.wav')
                self.sound63 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#S.wav')
                self.sound64 = None
                self.sound66 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#F.wav')
                self.sound68 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#G.wav')
                self.sound70 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#H.wav')
                self.sound71 = None
                self.sound72 = None
                self.sound73 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Q.wav')
                self.sound74 = None
                self.sound75 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#W.wav')
                self.sound76 = None
                self.sound77 = None
                self.sound78 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#R.wav')
                self.sound79 = None
                self.sound80 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#T.wav')
                self.sound81 = None
                self.sound82 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Y.wav')
                self.sound83 = None
                self.sound84 = pygame.mixer.Sound(r'resource\Windsong_Lyre\1.wav')
                self.sound85 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#1.wav')
                self.sound86 = pygame.mixer.Sound(r'resource\Windsong_Lyre\2.wav')
                self.sound87 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#2.wav')
                self.sound88 = pygame.mixer.Sound(r'resource\Windsong_Lyre\3.wav')
                self.sound89 = pygame.mixer.Sound(r'resource\Windsong_Lyre\4.wav')
                self.sound90 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#4.wav')
                self.sound91 = pygame.mixer.Sound(r'resource\Windsong_Lyre\5.wav')
                self.sound92 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#5.wav')
                self.sound93 = pygame.mixer.Sound(r'resource\Windsong_Lyre\6.wav')
                self.sound94 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#6.wav')
                self.sound95 = pygame.mixer.Sound(r'resource\Windsong_Lyre\7.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.presets = {
                "映射规则:风物之诗琴-基础21键": {
                    48: {"type": "key", "value": 'z'},
                    50: {"type": "key", "value": 'x'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    55: {"type": "key", "value": 'b'},
                    57: {"type": "key", "value": 'n'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    62: {"type": "key", "value": 's'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    67: {"type": "key", "value": 'g'},
                    69: {"type": "key", "value": 'h'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    74: {"type": "key", "value": 'w'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    79: {"type": "key", "value": 't'},
                    81: {"type": "key", "value": 'y'},
                    83: {"type": "key", "value": 'u'}
                },
                "映射规则:风物之诗琴-36转21键": {
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "key", "value": 'x'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "key", "value": 'b'},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "key", "value": 'n'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "key", "value": 's'},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "key", "value": 'g'},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "key", "value": 'h'},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "key", "value": 'w'},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "key", "value": 'e'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "key", "value": 't'},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "key", "value": 'y'},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "key", "value": 'u'},
                    83: {"type": "key", "value": 'u'}
                },
                "映射规则:风物之诗琴-拓展36键": {
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "audio", "value": self.sound49},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "audio", "value": self.sound51},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "audio", "value": self.sound54},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "audio", "value": self.sound56},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "audio", "value": self.sound58},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "audio", "value": self.sound63},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "audio", "value": self.sound70},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "audio", "value": self.sound73},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "audio", "value": self.sound75},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "audio", "value": self.sound78},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "audio", "value": self.sound80},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "audio", "value": self.sound82},
                    83: {"type": "key", "value": 'u'}
                },
                "映射规则:风物之诗琴-60转21键": {
                    36: {"type": "key", "value": 'z'},
                    37: {"type": "key", "value": 'x'},
                    38: {"type": "key", "value": 'x'},
                    39: {"type": "key", "value": 'c'},
                    40: {"type": "key", "value": 'c'},
                    41: {"type": "key", "value": 'v'},
                    42: {"type": "key", "value": 'b'},
                    43: {"type": "key", "value": 'b'},
                    44: {"type": "key", "value": 'n'},
                    45: {"type": "key", "value": 'n'},
                    46: {"type": "key", "value": 'm'},
                    47: {"type": "key", "value": 'm'},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "key", "value": 'x'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "key", "value": 'b'},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "key", "value": 'n'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "key", "value": 's'},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "key", "value": 'g'},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "key", "value": 'h'},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "key", "value": 'w'},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "key", "value": 'e'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "key", "value": 't'},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "key", "value": 'y'},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "key", "value": 'u'},
                    83: {"type": "key", "value": 'u'},
                    84: {"type": "key", "value": 'q'},
                    85: {"type": "key", "value": 'w'},
                    86: {"type": "key", "value": 'w'},
                    87: {"type": "key", "value": 'e'},
                    88: {"type": "key", "value": 'e'},
                    89: {"type": "key", "value": 'r'},
                    90: {"type": "key", "value": 't'},
                    91: {"type": "key", "value": 't'},
                    92: {"type": "key", "value": 'y'},
                    93: {"type": "key", "value": 'y'},
                    94: {"type": "key", "value": 'u'},
                    95: {"type": "key", "value": 'u'}
                },
                "映射规则:风物之诗琴-拓展60键": {
                    36: {"type": "audio", "value": self.sound36},
                    37: {"type": "audio", "value": self.sound37},
                    38: {"type": "audio", "value": self.sound38},
                    39: {"type": "audio", "value": self.sound39},
                    40: {"type": "audio", "value": self.sound40},
                    41: {"type": "audio", "value": self.sound41},
                    42: {"type": "audio", "value": self.sound42},
                    43: {"type": "audio", "value": self.sound43},
                    44: {"type": "audio", "value": self.sound44},
                    45: {"type": "audio", "value": self.sound45},
                    46: {"type": "audio", "value": self.sound46},
                    47: {"type": "audio", "value": self.sound47},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "audio", "value": self.sound49},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "audio", "value": self.sound51},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "audio", "value": self.sound54},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "audio", "value": self.sound56},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "audio", "value": self.sound58},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "audio", "value": self.sound63},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "audio", "value": self.sound70},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "audio", "value": self.sound73},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "audio", "value": self.sound75},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "audio", "value": self.sound78},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "audio", "value": self.sound80},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "audio", "value": self.sound82},
                    83: {"type": "key", "value": 'u'},
                    84: {"type": "audio", "value": self.sound84},
                    85: {"type": "audio", "value": self.sound85},
                    86: {"type": "audio", "value": self.sound86},
                    87: {"type": "audio", "value": self.sound87},
                    88: {"type": "audio", "value": self.sound88},
                    89: {"type": "audio", "value": self.sound89},
                    90: {"type": "audio", "value": self.sound90},
                    91: {"type": "audio", "value": self.sound91},
                    92: {"type": "audio", "value": self.sound92},
                    93: {"type": "audio", "value": self.sound93},
                    94: {"type": "audio", "value": self.sound94},
                    95: {"type": "audio", "value": self.sound95}
                }
            }
        if 5 <= index <= 9:
            try:
                self.sound36 = pygame.mixer.Sound(r'resource\Floral_Zither\,.wav')
                self.sound37 = pygame.mixer.Sound(r'resource\Floral_Zither\#,.wav')
                self.sound38 = pygame.mixer.Sound(r'resource\Floral_Zither\..wav')
                self.sound39 = pygame.mixer.Sound(r'resource\Floral_Zither\#..wav')
                self.sound40 = pygame.mixer.Sound(r'resource\Floral_Zither\xie.wav')
                self.sound41 = pygame.mixer.Sound(r'resource\Floral_Zither\;.wav')
                self.sound42 = pygame.mixer.Sound(r'resource\Floral_Zither\#;.wav')
                self.sound43 = pygame.mixer.Sound(r'resource\Floral_Zither\'.wav')
                self.sound44 = pygame.mixer.Sound('resource\\Floral_Zither\\#\'.wav')
                self.sound45 = pygame.mixer.Sound(r'resource\Floral_Zither\[.wav')
                self.sound46 = pygame.mixer.Sound(r'resource\Floral_Zither\#[.wav')
                self.sound47 = pygame.mixer.Sound(r'resource\Floral_Zither\].wav')
                self.sound49 = pygame.mixer.Sound(r'resource\Floral_Zither\#Z.wav')
                self.sound51 = pygame.mixer.Sound(r'resource\Floral_Zither\#X.wav')
                self.sound52 = None
                self.sound53 = None
                self.sound54 = pygame.mixer.Sound(r'resource\Floral_Zither\#V.wav')
                self.sound55 = None
                self.sound56 = pygame.mixer.Sound(r'resource\Floral_Zither\#B.wav')
                self.sound57 = None
                self.sound58 = pygame.mixer.Sound(r'resource\Floral_Zither\#N.wav')
                self.sound59 = None
                self.sound61 = pygame.mixer.Sound(r'resource\Floral_Zither\#A.wav')
                self.sound63 = pygame.mixer.Sound(r'resource\Floral_Zither\#S.wav')
                self.sound64 = None
                self.sound66 = pygame.mixer.Sound(r'resource\Floral_Zither\#F.wav')
                self.sound68 = pygame.mixer.Sound(r'resource\Floral_Zither\#G.wav')
                self.sound70 = pygame.mixer.Sound(r'resource\Floral_Zither\#H.wav')
                self.sound71 = None
                self.sound72 = None
                self.sound73 = pygame.mixer.Sound(r'resource\Floral_Zither\#Q.wav')
                self.sound74 = None
                self.sound75 = pygame.mixer.Sound(r'resource\Floral_Zither\#W.wav')
                self.sound76 = None
                self.sound77 = None
                self.sound78 = pygame.mixer.Sound(r'resource\Floral_Zither\#R.wav')
                self.sound79 = None
                self.sound80 = pygame.mixer.Sound(r'resource\Floral_Zither\#T.wav')
                self.sound81 = None
                self.sound82 = pygame.mixer.Sound(r'resource\Floral_Zither\#Y.wav')
                self.sound83 = None
                self.sound84 = pygame.mixer.Sound(r'resource\Floral_Zither\1.wav')
                self.sound85 = pygame.mixer.Sound(r'resource\Floral_Zither\#1.wav')
                self.sound86 = pygame.mixer.Sound(r'resource\Floral_Zither\2.wav')
                self.sound87 = pygame.mixer.Sound(r'resource\Floral_Zither\#2.wav')
                self.sound88 = pygame.mixer.Sound(r'resource\Floral_Zither\3.wav')
                self.sound89 = pygame.mixer.Sound(r'resource\Floral_Zither\4.wav')
                self.sound90 = pygame.mixer.Sound(r'resource\Floral_Zither\#4.wav')
                self.sound91 = pygame.mixer.Sound(r'resource\Floral_Zither\5.wav')
                self.sound92 = pygame.mixer.Sound(r'resource\Floral_Zither\#5.wav')
                self.sound93 = pygame.mixer.Sound(r'resource\Floral_Zither\6.wav')
                self.sound94 = pygame.mixer.Sound(r'resource\Floral_Zither\#6.wav')
                self.sound95 = pygame.mixer.Sound(r'resource\Floral_Zither\7.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.presets = {
                "映射规则:镜花之琴-基础21键": {
                    48: {"type": "key", "value": 'z'},
                    50: {"type": "key", "value": 'x'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    55: {"type": "key", "value": 'b'},
                    57: {"type": "key", "value": 'n'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    62: {"type": "key", "value": 's'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    67: {"type": "key", "value": 'g'},
                    69: {"type": "key", "value": 'h'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    74: {"type": "key", "value": 'w'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    79: {"type": "key", "value": 't'},
                    81: {"type": "key", "value": 'y'},
                    83: {"type": "key", "value": 'u'}
                },
                "映射规则:镜花之琴-36转21键": {
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "key", "value": 'x'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "key", "value": 'b'},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "key", "value": 'n'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "key", "value": 's'},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "key", "value": 'g'},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "key", "value": 'h'},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "key", "value": 'w'},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "key", "value": 'e'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "key", "value": 't'},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "key", "value": 'y'},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "key", "value": 'u'},
                    83: {"type": "key", "value": 'u'}
                },
                "映射规则:镜花之琴-拓展36键": {
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "audio", "value": self.sound49},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "audio", "value": self.sound51},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "audio", "value": self.sound54},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "audio", "value": self.sound56},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "audio", "value": self.sound58},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "audio", "value": self.sound63},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "audio", "value": self.sound70},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "audio", "value": self.sound73},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "audio", "value": self.sound75},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "audio", "value": self.sound78},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "audio", "value": self.sound80},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "audio", "value": self.sound82},
                    83: {"type": "key", "value": 'u'}
                },
                "映射规则:镜花之琴-60转21键": {
                    36: {"type": "key", "value": 'z'},
                    37: {"type": "key", "value": 'x'},
                    38: {"type": "key", "value": 'x'},
                    39: {"type": "key", "value": 'c'},
                    40: {"type": "key", "value": 'c'},
                    41: {"type": "key", "value": 'v'},
                    42: {"type": "key", "value": 'b'},
                    43: {"type": "key", "value": 'b'},
                    44: {"type": "key", "value": 'n'},
                    45: {"type": "key", "value": 'n'},
                    46: {"type": "key", "value": 'm'},
                    47: {"type": "key", "value": 'm'},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "key", "value": 'x'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "key", "value": 'b'},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "key", "value": 'n'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "key", "value": 's'},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "key", "value": 'g'},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "key", "value": 'h'},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "key", "value": 'w'},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "key", "value": 'e'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "key", "value": 't'},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "key", "value": 'y'},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "key", "value": 'u'},
                    83: {"type": "key", "value": 'u'},
                    84: {"type": "key", "value": 'q'},
                    85: {"type": "key", "value": 'w'},
                    86: {"type": "key", "value": 'w'},
                    87: {"type": "key", "value": 'e'},
                    88: {"type": "key", "value": 'e'},
                    89: {"type": "key", "value": 'r'},
                    90: {"type": "key", "value": 't'},
                    91: {"type": "key", "value": 't'},
                    92: {"type": "key", "value": 'y'},
                    93: {"type": "key", "value": 'y'},
                    94: {"type": "key", "value": 'u'},
                    95: {"type": "key", "value": 'u'}
                },
                "映射规则:镜花之琴-拓展60键": {
                    36: {"type": "audio", "value": self.sound36},
                    37: {"type": "audio", "value": self.sound37},
                    38: {"type": "audio", "value": self.sound38},
                    39: {"type": "audio", "value": self.sound39},
                    40: {"type": "audio", "value": self.sound40},
                    41: {"type": "audio", "value": self.sound41},
                    42: {"type": "audio", "value": self.sound42},
                    43: {"type": "audio", "value": self.sound43},
                    44: {"type": "audio", "value": self.sound44},
                    45: {"type": "audio", "value": self.sound45},
                    46: {"type": "audio", "value": self.sound46},
                    47: {"type": "audio", "value": self.sound47},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "audio", "value": self.sound49},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "audio", "value": self.sound51},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "audio", "value": self.sound54},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "audio", "value": self.sound56},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "audio", "value": self.sound58},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "audio", "value": self.sound63},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "audio", "value": self.sound70},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "audio", "value": self.sound73},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "audio", "value": self.sound75},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "audio", "value": self.sound78},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "audio", "value": self.sound80},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "audio", "value": self.sound82},
                    83: {"type": "key", "value": 'u'},
                    84: {"type": "audio", "value": self.sound84},
                    85: {"type": "audio", "value": self.sound85},
                    86: {"type": "audio", "value": self.sound86},
                    87: {"type": "audio", "value": self.sound87},
                    88: {"type": "audio", "value": self.sound88},
                    89: {"type": "audio", "value": self.sound89},
                    90: {"type": "audio", "value": self.sound90},
                    91: {"type": "audio", "value": self.sound91},
                    92: {"type": "audio", "value": self.sound92},
                    93: {"type": "audio", "value": self.sound93},
                    94: {"type": "audio", "value": self.sound94},
                    95: {"type": "audio", "value": self.sound95}
                }
            }
        if 10 <= index <= 14:
            try:
                self.sound36 = pygame.mixer.Sound(r'resource\Vintage_Lyre\,.wav')
                self.sound37 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#,.wav')
                self.sound38 = pygame.mixer.Sound(r'resource\Vintage_Lyre\..wav')
                self.sound39 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#..wav')
                self.sound40 = pygame.mixer.Sound(r'resource\Vintage_Lyre\xie.wav')
                self.sound41 = pygame.mixer.Sound(r'resource\Vintage_Lyre\;.wav')
                self.sound42 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#;.wav')
                self.sound43 = pygame.mixer.Sound(r'resource\Vintage_Lyre\'.wav')
                self.sound44 = pygame.mixer.Sound('resource\\Vintage_Lyre\\#\'.wav')
                self.sound45 = pygame.mixer.Sound(r'resource\Vintage_Lyre\[.wav')
                self.sound46 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#[.wav')
                self.sound47 = pygame.mixer.Sound(r'resource\Vintage_Lyre\].wav')
                self.sound49 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#Z.wav')
                self.sound51 = None
                self.sound52 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#C.wav')
                self.sound54 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#V.wav')
                self.sound56 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#B.wav')
                self.sound58 = None
                self.sound59 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#M.wav')
                self.sound61 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#A.wav')
                self.sound63 = None
                self.sound64 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#D.wav')
                self.sound66 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#F.wav')
                self.sound68 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#G.wav')
                self.sound70 = None
                self.sound71 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#J.wav')
                self.sound73 = None
                self.sound74 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#W.wav')
                self.sound75 = None
                self.sound76 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#E.wav')
                self.sound78 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#R.wav')
                self.sound80 = None
                self.sound81 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#Y.wav')
                self.sound82 = None
                self.sound83 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#U.wav')
                self.sound84 = pygame.mixer.Sound(r'resource\Vintage_Lyre\1.wav')
                self.sound85 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#1.wav')
                self.sound86 = pygame.mixer.Sound(r'resource\Vintage_Lyre\2.wav')
                self.sound87 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#2.wav')
                self.sound88 = pygame.mixer.Sound(r'resource\Vintage_Lyre\3.wav')
                self.sound89 = pygame.mixer.Sound(r'resource\Vintage_Lyre\4.wav')
                self.sound90 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#4.wav')
                self.sound91 = pygame.mixer.Sound(r'resource\Vintage_Lyre\5.wav')
                self.sound92 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#5.wav')
                self.sound93 = pygame.mixer.Sound(r'resource\Vintage_Lyre\6.wav')
                self.sound94 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#6.wav')
                self.sound95 = pygame.mixer.Sound(r'resource\Vintage_Lyre\7.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.presets = {
                "映射规则:老旧的诗琴-基础21键": {
                    48: {"type": "key", "value": 'z'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    55: {"type": "key", "value": 'b'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    67: {"type": "key", "value": 'g'},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "key", "value": 'w'},
                    75: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "key", "value": 'y'},
                    82: {"type": "key", "value": 'u'}
                },
                "映射规则:老旧的诗琴-36转21键": {
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "key", "value": 'x'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "key", "value": 'b'},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "key", "value": 'n'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "key", "value": 's'},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "key", "value": 'g'},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "key", "value": 'h'},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "key", "value": 'w'},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "key", "value": 'e'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "key", "value": 't'},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "key", "value": 'y'},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "key", "value": 'u'},
                    83: {"type": "key", "value": 'u'}
                },
                "映射规则:老旧的诗琴-拓展36键": {
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "audio", "value": self.sound49},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "audio", "value": self.sound52},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "audio", "value": self.sound54},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "audio", "value": self.sound56},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "audio", "value": self.sound59},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "audio", "value": self.sound64},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "audio", "value": self.sound71},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "audio", "value": self.sound73},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "key", "value": 'e'},
                    76: {"type": "audio", "value": self.sound76},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "audio", "value": self.sound78},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "audio", "value": self.sound80},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "key", "value": 'u'},
                    83: {"type": "audio", "value": self.sound83}
                },
                "映射规则:老旧的诗琴-60转21键": {
                    36: {"type": "key", "value": 'z'},
                    37: {"type": "key", "value": 'x'},
                    38: {"type": "key", "value": 'x'},
                    39: {"type": "key", "value": 'c'},
                    40: {"type": "key", "value": 'c'},
                    41: {"type": "key", "value": 'v'},
                    42: {"type": "key", "value": 'b'},
                    43: {"type": "key", "value": 'b'},
                    44: {"type": "key", "value": 'n'},
                    45: {"type": "key", "value": 'n'},
                    46: {"type": "key", "value": 'm'},
                    47: {"type": "key", "value": 'm'},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "key", "value": 'x'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "key", "value": 'b'},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "key", "value": 'n'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "key", "value": 's'},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "key", "value": 'g'},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "key", "value": 'h'},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "key", "value": 'w'},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "key", "value": 'e'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "key", "value": 't'},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "key", "value": 'y'},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "key", "value": 'u'},
                    83: {"type": "key", "value": 'u'},
                    84: {"type": "key", "value": 'q'},
                    85: {"type": "key", "value": 'w'},
                    86: {"type": "key", "value": 'w'},
                    87: {"type": "key", "value": 'e'},
                    88: {"type": "key", "value": 'e'},
                    89: {"type": "key", "value": 'r'},
                    90: {"type": "key", "value": 't'},
                    91: {"type": "key", "value": 't'},
                    92: {"type": "key", "value": 'y'},
                    93: {"type": "key", "value": 'y'},
                    94: {"type": "key", "value": 'u'},
                    95: {"type": "key", "value": 'u'}
                },
                "映射规则:老旧的诗琴-拓展60键": {
                    36: {"type": "audio", "value": self.sound36},
                    37: {"type": "audio", "value": self.sound37},
                    38: {"type": "audio", "value": self.sound38},
                    39: {"type": "audio", "value": self.sound39},
                    40: {"type": "audio", "value": self.sound40},
                    41: {"type": "audio", "value": self.sound41},
                    42: {"type": "audio", "value": self.sound42},
                    43: {"type": "audio", "value": self.sound43},
                    44: {"type": "audio", "value": self.sound44},
                    45: {"type": "audio", "value": self.sound45},
                    46: {"type": "audio", "value": self.sound46},
                    47: {"type": "audio", "value": self.sound47},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "audio", "value": self.sound49},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "audio", "value": self.sound52},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "audio", "value": self.sound54},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "audio", "value": self.sound56},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "audio", "value": self.sound59},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "audio", "value": self.sound64},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "audio", "value": self.sound71},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "key", "value": 'w'},
                    74: {"type": "audio", "value": self.sound74},
                    75: {"type": "key", "value": 'e'},
                    76: {"type": "audio", "value": self.sound76},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "audio", "value": self.sound78},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "key", "value": 'y'},
                    81: {"type": "audio", "value": self.sound81},
                    82: {"type": "key", "value": 'u'},
                    83: {"type": "audio", "value": self.sound83},
                    84: {"type": "audio", "value": self.sound84},
                    85: {"type": "audio", "value": self.sound85},
                    86: {"type": "audio", "value": self.sound86},
                    87: {"type": "audio", "value": self.sound87},
                    88: {"type": "audio", "value": self.sound88},
                    89: {"type": "audio", "value": self.sound89},
                    90: {"type": "audio", "value": self.sound90},
                    91: {"type": "audio", "value": self.sound91},
                    92: {"type": "audio", "value": self.sound92},
                    93: {"type": "audio", "value": self.sound93},
                    94: {"type": "audio", "value": self.sound94},
                    95: {"type": "audio", "value": self.sound95}
                }
            }
        if index == 15:
            self.presets = {
                "映射规则:晚风圆号-基础14键": {
                    60: {"type": "key", "value": 'a'},
                    62: {"type": "key", "value": 's'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    67: {"type": "key", "value": 'g'},
                    69: {"type": "key", "value": 'h'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    74: {"type": "key", "value": 'w'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    79: {"type": "key", "value": 't'},
                    81: {"type": "key", "value": 'y'},
                    83: {"type": "key", "value": 'u'}
                }
            }
        if 16 <= index <= 20:
            try:
                self.sound36 = pygame.mixer.Sound(r'resource\Ukulele\Q.wav')
                self.sound37 = None
                self.sound38 = pygame.mixer.Sound(r'resource\Ukulele\W.wav')
                self.sound39 = None
                self.sound40 = pygame.mixer.Sound(r'resource\Ukulele\E.wav')
                self.sound41 = pygame.mixer.Sound(r'resource\Ukulele\R.wav')
                self.sound42 = None
                self.sound43 = pygame.mixer.Sound(r'resource\Ukulele\T.wav')
                self.sound44 = None
                self.sound45 = pygame.mixer.Sound(r'resource\Ukulele\Y.wav')
                self.sound46 = None
                self.sound47 = pygame.mixer.Sound(r'resource\Ukulele\U.wav')
                self.sound48 = pygame.mixer.Sound(r'resource\Ukulele\,.wav')
                self.sound49 = pygame.mixer.Sound(r'resource\Ukulele\#,.wav')
                self.sound50 = pygame.mixer.Sound(r'resource\Ukulele\..wav')
                self.sound51 = pygame.mixer.Sound(r'resource\Ukulele\#..wav')
                self.sound52 = pygame.mixer.Sound(r'resource\Ukulele\xie.wav')
                self.sound53 = pygame.mixer.Sound(r'resource\Ukulele\;.wav')
                self.sound54 = pygame.mixer.Sound(r'resource\Ukulele\#;.wav')
                self.sound55 = pygame.mixer.Sound(r'resource\Ukulele\'.wav')
                self.sound56 = pygame.mixer.Sound('resource\\Ukulele\\#\'.wav')
                self.sound57 = pygame.mixer.Sound(r'resource\Ukulele\[.wav')
                self.sound58 = pygame.mixer.Sound(r'resource\Ukulele\#[.wav')
                self.sound59 = pygame.mixer.Sound(r'resource\Ukulele\].wav')
                self.sound61 = pygame.mixer.Sound(r'resource\Ukulele\#Z.wav')
                self.sound63 = pygame.mixer.Sound(r'resource\Ukulele\#X.wav')
                self.sound64 = None
                self.sound66 = pygame.mixer.Sound(r'resource\Ukulele\#V.wav')
                self.sound68 = pygame.mixer.Sound(r'resource\Ukulele\#B.wav')
                self.sound70 = pygame.mixer.Sound(r'resource\Ukulele\#N.wav')
                self.sound71 = None
                self.sound73 = pygame.mixer.Sound(r'resource\Ukulele\#A.wav')
                self.sound74 = None
                self.sound75 = pygame.mixer.Sound(r'resource\Ukulele\#S.wav')
                self.sound76 = None
                self.sound78 = pygame.mixer.Sound(r'resource\Ukulele\#F.wav')
                self.sound80 = pygame.mixer.Sound(r'resource\Ukulele\#G.wav')
                self.sound81 = None
                self.sound82 = pygame.mixer.Sound(r'resource\Ukulele\#H.wav')
                self.sound83 = None
                self.sound84 = None
                self.sound85 = None
                self.sound86 = None
                self.sound87 = None
                self.sound88 = None
                self.sound89 = None
                self.sound90 = None
                self.sound91 = None
                self.sound92 = None
                self.sound93 = None
                self.sound94 = None
                self.sound95 = None
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.presets = {
                "映射规则:悠可琴-基础21键": {
                    36: {"type": "key", "value": 'q'},
                    38: {"type": "key", "value": 'w'},
                    40: {"type": "key", "value": 'e'},
                    41: {"type": "key", "value": 'r'},
                    43: {"type": "key", "value": 't'},
                    45: {"type": "key", "value": 'y'},
                    47: {"type": "key", "value": 'u'},
                    60: {"type": "key", "value": 'z'},
                    62: {"type": "key", "value": 'x'},
                    64: {"type": "key", "value": 'c'},
                    65: {"type": "key", "value": 'v'},
                    67: {"type": "key", "value": 'b'},
                    69: {"type": "key", "value": 'n'},
                    71: {"type": "key", "value": 'm'},
                    72: {"type": "key", "value": 'a'},
                    74: {"type": "key", "value": 's'},
                    76: {"type": "key", "value": 'd'},
                    77: {"type": "key", "value": 'f'},
                    79: {"type": "key", "value": 'g'},
                    81: {"type": "key", "value": 'h'},
                    83: {"type": "key", "value": 'j'}
                },
                "映射规则:悠可琴-31转21键": {
                    36: {"type": "key", "value": 'q'},
                    38: {"type": "key", "value": 'w'},
                    40: {"type": "key", "value": 'e'},
                    41: {"type": "key", "value": 'r'},
                    43: {"type": "key", "value": 't'},
                    45: {"type": "key", "value": 'y'},
                    47: {"type": "key", "value": 'u'},
                    60: {"type": "key", "value": 'z'},
                    61: {"type": "key", "value": 'x'},
                    62: {"type": "key", "value": 'x'},
                    63: {"type": "key", "value": 'c'},
                    64: {"type": "key", "value": 'c'},
                    65: {"type": "key", "value": 'v'},
                    66: {"type": "key", "value": 'b'},
                    67: {"type": "key", "value": 'b'},
                    68: {"type": "key", "value": 'n'},
                    69: {"type": "key", "value": 'n'},
                    70: {"type": "key", "value": 'm'},
                    71: {"type": "key", "value": 'm'},
                    72: {"type": "key", "value": 'a'},
                    73: {"type": "key", "value": 's'},
                    74: {"type": "key", "value": 's'},
                    75: {"type": "key", "value": 'd'},
                    76: {"type": "key", "value": 'd'},
                    77: {"type": "key", "value": 'f'},
                    78: {"type": "key", "value": 'g'},
                    79: {"type": "key", "value": 'g'},
                    80: {"type": "key", "value": 'h'},
                    81: {"type": "key", "value": 'h'},
                    82: {"type": "key", "value": 'j'},
                    83: {"type": "key", "value": 'j'}
                },
                "映射规则:悠可琴-拓展31键": {
                    36: {"type": "key", "value": 'q'},
                    38: {"type": "key", "value": 'w'},
                    40: {"type": "key", "value": 'e'},
                    41: {"type": "key", "value": 'r'},
                    43: {"type": "key", "value": 't'},
                    45: {"type": "key", "value": 'y'},
                    47: {"type": "key", "value": 'u'},
                    60: {"type": "key", "value": 'z'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 'x'},
                    63: {"type": "audio", "value": self.sound63},
                    64: {"type": "key", "value": 'c'},
                    65: {"type": "key", "value": 'v'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'b'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'n'},
                    70: {"type": "audio", "value": self.sound70},
                    71: {"type": "key", "value": 'm'},
                    72: {"type": "key", "value": 'a'},
                    73: {"type": "audio", "value": self.sound73},
                    74: {"type": "key", "value": 's'},
                    75: {"type": "audio", "value": self.sound75},
                    76: {"type": "key", "value": 'd'},
                    77: {"type": "key", "value": 'f'},
                    78: {"type": "audio", "value": self.sound78},
                    79: {"type": "key", "value": 'g'},
                    80: {"type": "audio", "value": self.sound80},
                    81: {"type": "key", "value": 'h'},
                    82: {"type": "audio", "value": self.sound82},
                    83: {"type": "key", "value": 'j'}
                },
                "映射规则:悠可琴-43转21键": {
                    36: {"type": "key", "value": 'q'},
                    38: {"type": "key", "value": 'w'},
                    40: {"type": "key", "value": 'e'},
                    41: {"type": "key", "value": 'r'},
                    43: {"type": "key", "value": 't'},
                    45: {"type": "key", "value": 'y'},
                    47: {"type": "key", "value": 'u'},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "key", "value": 'x'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "key", "value": 'b'},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "key", "value": 'n'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'z'},
                    61: {"type": "key", "value": 'x'},
                    62: {"type": "key", "value": 'x'},
                    63: {"type": "key", "value": 'c'},
                    64: {"type": "key", "value": 'c'},
                    65: {"type": "key", "value": 'v'},
                    66: {"type": "key", "value": 'b'},
                    67: {"type": "key", "value": 'b'},
                    68: {"type": "key", "value": 'n'},
                    69: {"type": "key", "value": 'n'},
                    70: {"type": "key", "value": 'm'},
                    71: {"type": "key", "value": 'm'},
                    72: {"type": "key", "value": 'a'},
                    73: {"type": "key", "value": 's'},
                    74: {"type": "key", "value": 's'},
                    75: {"type": "key", "value": 'd'},
                    76: {"type": "key", "value": 'd'},
                    77: {"type": "key", "value": 'f'},
                    78: {"type": "key", "value": 'g'},
                    79: {"type": "key", "value": 'g'},
                    80: {"type": "key", "value": 'h'},
                    81: {"type": "key", "value": 'h'},
                    82: {"type": "key", "value": 'j'},
                    83: {"type": "key", "value": 'j'}
                },
                "映射规则:悠可琴-拓展43键": {
                    36: {"type": "key", "value": 'q'},
                    38: {"type": "key", "value": 'w'},
                    40: {"type": "key", "value": 'e'},
                    41: {"type": "key", "value": 'r'},
                    43: {"type": "key", "value": 't'},
                    45: {"type": "key", "value": 'y'},
                    47: {"type": "key", "value": 'u'},
                    48: {"type": "audio", "value": self.sound48},
                    49: {"type": "audio", "value": self.sound49},
                    50: {"type": "audio", "value": self.sound50},
                    51: {"type": "audio", "value": self.sound51},
                    52: {"type": "audio", "value": self.sound52},
                    53: {"type": "audio", "value": self.sound53},
                    54: {"type": "audio", "value": self.sound54},
                    55: {"type": "audio", "value": self.sound55},
                    56: {"type": "audio", "value": self.sound56},
                    57: {"type": "audio", "value": self.sound57},
                    58: {"type": "audio", "value": self.sound58},
                    59: {"type": "audio", "value": self.sound59},
                    60: {"type": "key", "value": 'z'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 'x'},
                    63: {"type": "audio", "value": self.sound63},
                    64: {"type": "key", "value": 'c'},
                    65: {"type": "key", "value": 'v'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'b'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'n'},
                    70: {"type": "audio", "value": self.sound70},
                    71: {"type": "key", "value": 'm'},
                    72: {"type": "key", "value": 'a'},
                    73: {"type": "audio", "value": self.sound73},
                    74: {"type": "key", "value": 's'},
                    75: {"type": "audio", "value": self.sound75},
                    76: {"type": "key", "value": 'd'},
                    77: {"type": "key", "value": 'f'},
                    78: {"type": "audio", "value": self.sound78},
                    79: {"type": "key", "value": 'g'},
                    80: {"type": "audio", "value": self.sound80},
                    81: {"type": "key", "value": 'h'},
                    82: {"type": "audio", "value": self.sound82},
                    83: {"type": "key", "value": 'j'}
                }
            }
        if 21 <= index <= 25:
            try:
                self.sound36 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\Q.wav')
                self.sound37 = None
                self.sound38 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\W.wav')
                self.sound39 = None
                self.sound40 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\E.wav')
                self.sound41 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\R.wav')
                self.sound42 = None
                self.sound43 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\T.wav')
                self.sound44 = None
                self.sound45 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\Y.wav')
                self.sound46 = None
                self.sound47 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\U.wav')
                self.sound49 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#Z.wav')
                self.sound51 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#X.wav')
                self.sound52 = None
                self.sound54 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#V.wav')
                self.sound56 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#B.wav')
                self.sound58 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#N.wav')
                self.sound59 = None
                self.sound61 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#A.wav')
                self.sound63 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#S.wav')
                self.sound64 = None
                self.sound66 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#F.wav')
                self.sound68 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#G.wav')
                self.sound70 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#H.wav')
                self.sound71 = None
                self.sound72 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\1.wav')
                self.sound73 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#1.wav')
                self.sound74 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\2.wav')
                self.sound75 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#2.wav')
                self.sound76 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\3.wav')
                self.sound77 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\4.wav')
                self.sound78 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#4.wav')
                self.sound79 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\5.wav')
                self.sound80 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#5.wav')
                self.sound81 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\6.wav')
                self.sound82 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#6.wav')
                self.sound83 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\7.wav')
                self.sound84 = None
                self.sound85 = None
                self.sound86 = None
                self.sound87 = None
                self.sound88 = None
                self.sound89 = None
                self.sound90 = None
                self.sound91 = None
                self.sound92 = None
                self.sound93 = None
                self.sound94 = None
                self.sound95 = None
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.presets = {
                "映射规则:「余音」-基础21键": {
                    36: {"type": "key", "value": 'q'},
                    38: {"type": "key", "value": 'w'},
                    40: {"type": "key", "value": 'e'},
                    41: {"type": "key", "value": 'r'},
                    43: {"type": "key", "value": 't'},
                    45: {"type": "key", "value": 'y'},
                    47: {"type": "key", "value": 'u'},
                    48: {"type": "key", "value": 'z'},
                    50: {"type": "key", "value": 'x'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    55: {"type": "key", "value": 'b'},
                    57: {"type": "key", "value": 'n'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    62: {"type": "key", "value": 's'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    67: {"type": "key", "value": 'g'},
                    69: {"type": "key", "value": 'h'},
                    71: {"type": "key", "value": 'j'}
                },
                "映射规则:「余音」-31转21键": {
                    36: {"type": "key", "value": 'q'},
                    38: {"type": "key", "value": 'w'},
                    40: {"type": "key", "value": 'e'},
                    41: {"type": "key", "value": 'r'},
                    43: {"type": "key", "value": 't'},
                    45: {"type": "key", "value": 'y'},
                    47: {"type": "key", "value": 'u'},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "key", "value": 'x'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "key", "value": 'b'},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "key", "value": 'n'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "key", "value": 's'},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "key", "value": 'g'},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "key", "value": 'h'},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "key", "value": 'j'}
                },
                "映射规则:「余音」-拓展31键": {
                    36: {"type": "key", "value": 'q'},
                    38: {"type": "key", "value": 'w'},
                    40: {"type": "key", "value": 'e'},
                    41: {"type": "key", "value": 'r'},
                    43: {"type": "key", "value": 't'},
                    45: {"type": "key", "value": 'y'},
                    47: {"type": "key", "value": 'u'},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "audio", "value": self.sound49},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "audio", "value": self.sound51},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "audio", "value": self.sound54},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "audio", "value": self.sound56},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "audio", "value": self.sound58},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "audio", "value": self.sound63},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "audio", "value": self.sound70},
                    71: {"type": "key", "value": 'j'}
                },
                "映射规则:「余音」-43转21键": {
                    36: {"type": "key", "value": 'q'},
                    38: {"type": "key", "value": 'w'},
                    40: {"type": "key", "value": 'e'},
                    41: {"type": "key", "value": 'r'},
                    43: {"type": "key", "value": 't'},
                    45: {"type": "key", "value": 'y'},
                    47: {"type": "key", "value": 'u'},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "key", "value": 'x'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "key", "value": 'b'},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "key", "value": 'n'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "key", "value": 's'},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "key", "value": 'g'},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "key", "value": 'h'},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'a'},
                    73: {"type": "key", "value": 's'},
                    74: {"type": "key", "value": 's'},
                    75: {"type": "key", "value": 'd'},
                    76: {"type": "key", "value": 'd'},
                    77: {"type": "key", "value": 'f'},
                    78: {"type": "key", "value": 'g'},
                    79: {"type": "key", "value": 'g'},
                    80: {"type": "key", "value": 'h'},
                    81: {"type": "key", "value": 'h'},
                    82: {"type": "key", "value": 'j'},
                    83: {"type": "key", "value": 'j'}
                },
                "映射规则:「余音」-拓展43键": {
                    36: {"type": "key", "value": 'q'},
                    38: {"type": "key", "value": 'w'},
                    40: {"type": "key", "value": 'e'},
                    41: {"type": "key", "value": 'r'},
                    43: {"type": "key", "value": 't'},
                    45: {"type": "key", "value": 'y'},
                    47: {"type": "key", "value": 'u'},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "audio", "value": self.sound49},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "audio", "value": self.sound51},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "audio", "value": self.sound54},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "audio", "value": self.sound56},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "audio", "value": self.sound58},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "audio", "value": self.sound63},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "audio", "value": self.sound70},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "audio", "value": self.sound72},
                    73: {"type": "audio", "value": self.sound73},
                    74: {"type": "audio", "value": self.sound74},
                    75: {"type": "audio", "value": self.sound75},
                    76: {"type": "audio", "value": self.sound76},
                    77: {"type": "audio", "value": self.sound77},
                    78: {"type": "audio", "value": self.sound78},
                    79: {"type": "audio", "value": self.sound79},
                    80: {"type": "audio", "value": self.sound80},
                    81: {"type": "audio", "value": self.sound81},
                    82: {"type": "audio", "value": self.sound82},
                    83: {"type": "audio", "value": self.sound83}
                }
            }
        if 26 <= index <= 30:
            try:
                self.sound36 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\,.wav')
                self.sound37 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#,.wav')
                self.sound38 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\..wav')
                self.sound39 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#..wav')
                self.sound40 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\xie.wav')
                self.sound41 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\;.wav')
                self.sound42 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#;.wav')
                self.sound43 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\'.wav')
                self.sound44 = pygame.mixer.Sound('resource\\Leaping_Spirit_Piano\\#\'.wav')
                self.sound45 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\[.wav')
                self.sound46 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#[.wav')
                self.sound47 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\].wav')
                self.sound49 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#Z.wav')
                self.sound51 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#X.wav')
                self.sound52 = None
                self.sound53 = None
                self.sound54 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#V.wav')
                self.sound55 = None
                self.sound56 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#B.wav')
                self.sound57 = None
                self.sound58 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#N.wav')
                self.sound59 = None
                self.sound61 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#A.wav')
                self.sound63 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#S.wav')
                self.sound64 = None
                self.sound66 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#F.wav')
                self.sound68 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#G.wav')
                self.sound70 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#H.wav')
                self.sound71 = None
                self.sound72 = None
                self.sound73 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#Q.wav')
                self.sound74 = None
                self.sound75 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#W.wav')
                self.sound76 = None
                self.sound77 = None
                self.sound78 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#R.wav')
                self.sound79 = None
                self.sound80 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#T.wav')
                self.sound81 = None
                self.sound82 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#Y.wav')
                self.sound83 = None
                self.sound84 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\1.wav')
                self.sound85 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#1.wav')
                self.sound86 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\2.wav')
                self.sound87 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#2.wav')
                self.sound88 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\3.wav')
                self.sound89 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\4.wav')
                self.sound90 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#4.wav')
                self.sound91 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\5.wav')
                self.sound92 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#5.wav')
                self.sound93 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\6.wav')
                self.sound94 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#6.wav')
                self.sound95 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\7.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.presets = {
                "映射规则:跃律琴-基础21键": {
                    48: {"type": "key", "value": 'z'},
                    50: {"type": "key", "value": 'x'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    55: {"type": "key", "value": 'b'},
                    57: {"type": "key", "value": 'n'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    62: {"type": "key", "value": 's'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    67: {"type": "key", "value": 'g'},
                    69: {"type": "key", "value": 'h'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    74: {"type": "key", "value": 'w'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    79: {"type": "key", "value": 't'},
                    81: {"type": "key", "value": 'y'},
                    83: {"type": "key", "value": 'u'}
                },
                "映射规则:跃律琴-36转21键": {
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "key", "value": 'x'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "key", "value": 'b'},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "key", "value": 'n'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "key", "value": 's'},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "key", "value": 'g'},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "key", "value": 'h'},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "key", "value": 'w'},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "key", "value": 'e'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "key", "value": 't'},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "key", "value": 'y'},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "key", "value": 'u'},
                    83: {"type": "key", "value": 'u'}
                },
                "映射规则:跃律琴-拓展36键": {
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "audio", "value": self.sound49},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "audio", "value": self.sound51},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "audio", "value": self.sound54},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "audio", "value": self.sound56},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "audio", "value": self.sound58},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "audio", "value": self.sound63},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "audio", "value": self.sound70},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "audio", "value": self.sound73},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "audio", "value": self.sound75},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "audio", "value": self.sound78},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "audio", "value": self.sound80},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "audio", "value": self.sound82},
                    83: {"type": "key", "value": 'u'}
                },
                "映射规则:跃律琴-60转21键": {
                    36: {"type": "key", "value": 'z'},
                    37: {"type": "key", "value": 'x'},
                    38: {"type": "key", "value": 'x'},
                    39: {"type": "key", "value": 'c'},
                    40: {"type": "key", "value": 'c'},
                    41: {"type": "key", "value": 'v'},
                    42: {"type": "key", "value": 'b'},
                    43: {"type": "key", "value": 'b'},
                    44: {"type": "key", "value": 'n'},
                    45: {"type": "key", "value": 'n'},
                    46: {"type": "key", "value": 'm'},
                    47: {"type": "key", "value": 'm'},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "key", "value": 'x'},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "key", "value": 'c'},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "key", "value": 'b'},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "key", "value": 'n'},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "key", "value": 'm'},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "key", "value": 's'},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "key", "value": 'd'},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "key", "value": 'g'},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "key", "value": 'h'},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "key", "value": 'j'},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "key", "value": 'w'},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "key", "value": 'e'},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "key", "value": 't'},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "key", "value": 'y'},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "key", "value": 'u'},
                    83: {"type": "key", "value": 'u'},
                    84: {"type": "key", "value": 'q'},
                    85: {"type": "key", "value": 'w'},
                    86: {"type": "key", "value": 'w'},
                    87: {"type": "key", "value": 'e'},
                    88: {"type": "key", "value": 'e'},
                    89: {"type": "key", "value": 'r'},
                    90: {"type": "key", "value": 't'},
                    91: {"type": "key", "value": 't'},
                    92: {"type": "key", "value": 'y'},
                    93: {"type": "key", "value": 'y'},
                    94: {"type": "key", "value": 'u'},
                    95: {"type": "key", "value": 'u'}
                },
                "映射规则:跃律琴-拓展60键": {
                    36: {"type": "audio", "value": self.sound36},
                    37: {"type": "audio", "value": self.sound37},
                    38: {"type": "audio", "value": self.sound38},
                    39: {"type": "audio", "value": self.sound39},
                    40: {"type": "audio", "value": self.sound40},
                    41: {"type": "audio", "value": self.sound41},
                    42: {"type": "audio", "value": self.sound42},
                    43: {"type": "audio", "value": self.sound43},
                    44: {"type": "audio", "value": self.sound44},
                    45: {"type": "audio", "value": self.sound45},
                    46: {"type": "audio", "value": self.sound46},
                    47: {"type": "audio", "value": self.sound47},
                    48: {"type": "key", "value": 'z'},
                    49: {"type": "audio", "value": self.sound49},
                    50: {"type": "key", "value": 'x'},
                    51: {"type": "audio", "value": self.sound51},
                    52: {"type": "key", "value": 'c'},
                    53: {"type": "key", "value": 'v'},
                    54: {"type": "audio", "value": self.sound54},
                    55: {"type": "key", "value": 'b'},
                    56: {"type": "audio", "value": self.sound56},
                    57: {"type": "key", "value": 'n'},
                    58: {"type": "audio", "value": self.sound58},
                    59: {"type": "key", "value": 'm'},
                    60: {"type": "key", "value": 'a'},
                    61: {"type": "audio", "value": self.sound61},
                    62: {"type": "key", "value": 's'},
                    63: {"type": "audio", "value": self.sound63},
                    64: {"type": "key", "value": 'd'},
                    65: {"type": "key", "value": 'f'},
                    66: {"type": "audio", "value": self.sound66},
                    67: {"type": "key", "value": 'g'},
                    68: {"type": "audio", "value": self.sound68},
                    69: {"type": "key", "value": 'h'},
                    70: {"type": "audio", "value": self.sound70},
                    71: {"type": "key", "value": 'j'},
                    72: {"type": "key", "value": 'q'},
                    73: {"type": "audio", "value": self.sound73},
                    74: {"type": "key", "value": 'w'},
                    75: {"type": "audio", "value": self.sound75},
                    76: {"type": "key", "value": 'e'},
                    77: {"type": "key", "value": 'r'},
                    78: {"type": "audio", "value": self.sound78},
                    79: {"type": "key", "value": 't'},
                    80: {"type": "audio", "value": self.sound80},
                    81: {"type": "key", "value": 'y'},
                    82: {"type": "audio", "value": self.sound82},
                    83: {"type": "key", "value": 'u'},
                    84: {"type": "audio", "value": self.sound84},
                    85: {"type": "audio", "value": self.sound85},
                    86: {"type": "audio", "value": self.sound86},
                    87: {"type": "audio", "value": self.sound87},
                    88: {"type": "audio", "value": self.sound88},
                    89: {"type": "audio", "value": self.sound89},
                    90: {"type": "audio", "value": self.sound90},
                    91: {"type": "audio", "value": self.sound91},
                    92: {"type": "audio", "value": self.sound92},
                    93: {"type": "audio", "value": self.sound93},
                    94: {"type": "audio", "value": self.sound94},
                    95: {"type": "audio", "value": self.sound95}
                }
            }
        if 31 <= index <= 32:
            try:
                self.sound36 = pygame.mixer.Sound(r'resource\Piano\,.wav')
                self.sound37 = pygame.mixer.Sound(r'resource\Piano\#,.wav')
                self.sound38 = pygame.mixer.Sound(r'resource\Piano\..wav')
                self.sound39 = pygame.mixer.Sound(r'resource\Piano\#..wav')
                self.sound40 = pygame.mixer.Sound(r'resource\Piano\xie.wav')
                self.sound41 = pygame.mixer.Sound(r'resource\Piano\;.wav')
                self.sound42 = pygame.mixer.Sound(r'resource\Piano\#;.wav')
                self.sound43 = pygame.mixer.Sound(r'resource\Piano\'.wav')
                self.sound44 = pygame.mixer.Sound('resource\\Piano\\#\'.wav')
                self.sound45 = pygame.mixer.Sound(r'resource\Piano\[.wav')
                self.sound46 = pygame.mixer.Sound(r'resource\Piano\#[.wav')
                self.sound47 = pygame.mixer.Sound(r'resource\Piano\].wav')
                self.sound48 = pygame.mixer.Sound(r'resource\Piano\Z.wav')
                self.sound49 = pygame.mixer.Sound(r'resource\Piano\#Z.wav')
                self.sound50 = pygame.mixer.Sound(r'resource\Piano\X.wav')
                self.sound51 = pygame.mixer.Sound(r'resource\Piano\#X.wav')
                self.sound52 = pygame.mixer.Sound(r'resource\Piano\C.wav')
                self.sound53 = pygame.mixer.Sound(r'resource\Piano\V.wav')
                self.sound54 = pygame.mixer.Sound(r'resource\Piano\#V.wav')
                self.sound55 = pygame.mixer.Sound(r'resource\Piano\B.wav')
                self.sound56 = pygame.mixer.Sound(r'resource\Piano\#B.wav')
                self.sound57 = pygame.mixer.Sound(r'resource\Piano\N.wav')
                self.sound58 = pygame.mixer.Sound(r'resource\Piano\#N.wav')
                self.sound59 = pygame.mixer.Sound(r'resource\Piano\M.wav')
                self.sound60 = pygame.mixer.Sound(r'resource\Piano\A.wav')
                self.sound61 = pygame.mixer.Sound(r'resource\Piano\#A.wav')
                self.sound62 = pygame.mixer.Sound(r'resource\Piano\S.wav')
                self.sound63 = pygame.mixer.Sound(r'resource\Piano\#S.wav')
                self.sound64 = pygame.mixer.Sound(r'resource\Piano\D.wav')
                self.sound65 = pygame.mixer.Sound(r'resource\Piano\F.wav')
                self.sound66 = pygame.mixer.Sound(r'resource\Piano\#F.wav')
                self.sound67 = pygame.mixer.Sound(r'resource\Piano\G.wav')
                self.sound68 = pygame.mixer.Sound(r'resource\Piano\#G.wav')
                self.sound69 = pygame.mixer.Sound(r'resource\Piano\H.wav')
                self.sound70 = pygame.mixer.Sound(r'resource\Piano\#H.wav')
                self.sound71 = pygame.mixer.Sound(r'resource\Piano\J.wav')
                self.sound72 = pygame.mixer.Sound(r'resource\Piano\Q.wav')
                self.sound73 = pygame.mixer.Sound(r'resource\Piano\#Q.wav')
                self.sound74 = pygame.mixer.Sound(r'resource\Piano\W.wav')
                self.sound75 = pygame.mixer.Sound(r'resource\Piano\#W.wav')
                self.sound76 = pygame.mixer.Sound(r'resource\Piano\E.wav')
                self.sound77 = pygame.mixer.Sound(r'resource\Piano\R.wav')
                self.sound78 = pygame.mixer.Sound(r'resource\Piano\#R.wav')
                self.sound79 = pygame.mixer.Sound(r'resource\Piano\T.wav')
                self.sound80 = pygame.mixer.Sound(r'resource\Piano\#T.wav')
                self.sound81 = pygame.mixer.Sound(r'resource\Piano\Y.wav')
                self.sound82 = pygame.mixer.Sound(r'resource\Piano\#Y.wav')
                self.sound83 = pygame.mixer.Sound(r'resource\Piano\U.wav')
                self.sound84 = pygame.mixer.Sound(r'resource\Piano\1.wav')
                self.sound85 = pygame.mixer.Sound(r'resource\Piano\#1.wav')
                self.sound86 = pygame.mixer.Sound(r'resource\Piano\2.wav')
                self.sound87 = pygame.mixer.Sound(r'resource\Piano\#2.wav')
                self.sound88 = pygame.mixer.Sound(r'resource\Piano\3.wav')
                self.sound89 = pygame.mixer.Sound(r'resource\Piano\4.wav')
                self.sound90 = pygame.mixer.Sound(r'resource\Piano\#4.wav')
                self.sound91 = pygame.mixer.Sound(r'resource\Piano\5.wav')
                self.sound92 = pygame.mixer.Sound(r'resource\Piano\#5.wav')
                self.sound93 = pygame.mixer.Sound(r'resource\Piano\6.wav')
                self.sound94 = pygame.mixer.Sound(r'resource\Piano\#6.wav')
                self.sound95 = pygame.mixer.Sound(r'resource\Piano\7.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            
            self.presets = {
                "映射规则:钢琴-增强拓展21键": {
                    36: {"type": "key", "value": 'z', "audio": self.sound48},
                    37: {"type": "key", "value": 'x', "audio": self.sound50},
                    38: {"type": "key", "value": 'x', "audio": self.sound50},
                    39: {"type": "key", "value": 'c', "audio": self.sound52},
                    40: {"type": "key", "value": 'c', "audio": self.sound52},
                    41: {"type": "key", "value": 'v', "audio": self.sound53},
                    42: {"type": "key", "value": 'b', "audio": self.sound55},
                    43: {"type": "key", "value": 'b', "audio": self.sound55},
                    44: {"type": "key", "value": 'n', "audio": self.sound57},
                    45: {"type": "key", "value": 'n', "audio": self.sound57},
                    46: {"type": "key", "value": 'm', "audio": self.sound59},
                    47: {"type": "key", "value": 'm', "audio": self.sound59},
                    48: {"type": "key", "value": 'z', "audio": self.sound48},
                    49: {"type": "key", "value": 'x', "audio": self.sound50},
                    50: {"type": "key", "value": 'x', "audio": self.sound50},
                    51: {"type": "key", "value": 'c', "audio": self.sound52},
                    52: {"type": "key", "value": 'c', "audio": self.sound52},
                    53: {"type": "key", "value": 'v', "audio": self.sound53},
                    54: {"type": "key", "value": 'b', "audio": self.sound55},
                    55: {"type": "key", "value": 'b', "audio": self.sound55},
                    56: {"type": "key", "value": 'n', "audio": self.sound57},
                    57: {"type": "key", "value": 'n', "audio": self.sound57},
                    58: {"type": "key", "value": 'm', "audio": self.sound59},
                    59: {"type": "key", "value": 'm', "audio": self.sound59},
                    60: {"type": "key", "value": 'a', "audio": self.sound60},
                    61: {"type": "key", "value": 's', "audio": self.sound62},
                    62: {"type": "key", "value": 's', "audio": self.sound62},
                    63: {"type": "key", "value": 'd', "audio": self.sound64},
                    64: {"type": "key", "value": 'd', "audio": self.sound64},
                    65: {"type": "key", "value": 'f', "audio": self.sound65},
                    66: {"type": "key", "value": 'g', "audio": self.sound67},
                    67: {"type": "key", "value": 'g', "audio": self.sound67},
                    68: {"type": "key", "value": 'h', "audio": self.sound69},
                    69: {"type": "key", "value": 'h', "audio": self.sound69},
                    70: {"type": "key", "value": 'j', "audio": self.sound71},
                    71: {"type": "key", "value": 'j', "audio": self.sound71},
                    72: {"type": "key", "value": 'q', "audio": self.sound72},
                    73: {"type": "key", "value": 'w', "audio": self.sound74},
                    74: {"type": "key", "value": 'w', "audio": self.sound74},
                    75: {"type": "key", "value": 'e', "audio": self.sound76},
                    76: {"type": "key", "value": 'e', "audio": self.sound76},
                    77: {"type": "key", "value": 'r', "audio": self.sound77},
                    78: {"type": "key", "value": 't', "audio": self.sound79},
                    79: {"type": "key", "value": 't', "audio": self.sound79},
                    80: {"type": "key", "value": 'y', "audio": self.sound81},
                    81: {"type": "key", "value": 'y', "audio": self.sound81},
                    82: {"type": "key", "value": 'u', "audio": self.sound83},
                    83: {"type": "key", "value": 'u', "audio": self.sound83},
                    84: {"type": "key", "value": 'q', "audio": self.sound72},
                    85: {"type": "key", "value": 'w', "audio": self.sound74},
                    86: {"type": "key", "value": 'w', "audio": self.sound74},
                    87: {"type": "key", "value": 'e', "audio": self.sound76},
                    88: {"type": "key", "value": 'e', "audio": self.sound76},
                    89: {"type": "key", "value": 'r', "audio": self.sound77},
                    90: {"type": "key", "value": 't', "audio": self.sound79},
                    91: {"type": "key", "value": 't', "audio": self.sound79},
                    92: {"type": "key", "value": 'y', "audio": self.sound81},
                    93: {"type": "key", "value": 'y', "audio": self.sound81},
                    94: {"type": "key", "value": 'u', "audio": self.sound83},
                    95: {"type": "key", "value": 'u', "audio": self.sound83}
                },
                "映射规则:钢琴-增强拓展60键": {
                    36: {"type": "key", "value": 'z', "audio": self.sound36},
                    37: {"type": "key", "value": 'x', "audio": self.sound37},
                    38: {"type": "key", "value": 'x', "audio": self.sound38},
                    39: {"type": "key", "value": 'c', "audio": self.sound39},
                    40: {"type": "key", "value": 'c', "audio": self.sound40},
                    41: {"type": "key", "value": 'v', "audio": self.sound41},
                    42: {"type": "key", "value": 'b', "audio": self.sound42},
                    43: {"type": "key", "value": 'b', "audio": self.sound43},
                    44: {"type": "key", "value": 'n', "audio": self.sound44},
                    45: {"type": "key", "value": 'n', "audio": self.sound45},
                    46: {"type": "key", "value": 'm', "audio": self.sound46},
                    47: {"type": "key", "value": 'm', "audio": self.sound47},
                    48: {"type": "key", "value": 'z', "audio": self.sound48},
                    49: {"type": "key", "value": 'x', "audio": self.sound49},
                    50: {"type": "key", "value": 'x', "audio": self.sound50},
                    51: {"type": "key", "value": 'c', "audio": self.sound51},
                    52: {"type": "key", "value": 'c', "audio": self.sound52},
                    53: {"type": "key", "value": 'v', "audio": self.sound53},
                    54: {"type": "key", "value": 'b', "audio": self.sound54},
                    55: {"type": "key", "value": 'b', "audio": self.sound55},
                    56: {"type": "key", "value": 'n', "audio": self.sound56},
                    57: {"type": "key", "value": 'n', "audio": self.sound57},
                    58: {"type": "key", "value": 'm', "audio": self.sound58},
                    59: {"type": "key", "value": 'm', "audio": self.sound59},
                    60: {"type": "key", "value": 'a', "audio": self.sound60},
                    61: {"type": "key", "value": 's', "audio": self.sound61},
                    62: {"type": "key", "value": 's', "audio": self.sound62},
                    63: {"type": "key", "value": 'd', "audio": self.sound63},
                    64: {"type": "key", "value": 'd', "audio": self.sound64},
                    65: {"type": "key", "value": 'f', "audio": self.sound65},
                    66: {"type": "key", "value": 'g', "audio": self.sound66},
                    67: {"type": "key", "value": 'g', "audio": self.sound67},
                    68: {"type": "key", "value": 'h', "audio": self.sound68},
                    69: {"type": "key", "value": 'h', "audio": self.sound69},
                    70: {"type": "key", "value": 'j', "audio": self.sound70},
                    71: {"type": "key", "value": 'j', "audio": self.sound71},
                    72: {"type": "key", "value": 'q', "audio": self.sound72},
                    73: {"type": "key", "value": 'w', "audio": self.sound73},
                    74: {"type": "key", "value": 'w', "audio": self.sound74},
                    75: {"type": "key", "value": 'e', "audio": self.sound75},
                    76: {"type": "key", "value": 'e', "audio": self.sound76},
                    77: {"type": "key", "value": 'r', "audio": self.sound77},
                    78: {"type": "key", "value": 't', "audio": self.sound78},
                    79: {"type": "key", "value": 't', "audio": self.sound79},
                    80: {"type": "key", "value": 'y', "audio": self.sound80},
                    81: {"type": "key", "value": 'y', "audio": self.sound81},
                    82: {"type": "key", "value": 'u', "audio": self.sound82},
                    83: {"type": "key", "value": 'u', "audio": self.sound83},
                    84: {"type": "key", "value": 'q', "audio": self.sound84},
                    85: {"type": "key", "value": 'w', "audio": self.sound85},
                    86: {"type": "key", "value": 'w', "audio": self.sound86},
                    87: {"type": "key", "value": 'e', "audio": self.sound87},
                    88: {"type": "key", "value": 'e', "audio": self.sound88},
                    89: {"type": "key", "value": 'r', "audio": self.sound89},
                    90: {"type": "key", "value": 't', "audio": self.sound90},
                    91: {"type": "key", "value": 't', "audio": self.sound91},
                    92: {"type": "key", "value": 'y', "audio": self.sound92},
                    93: {"type": "key", "value": 'y', "audio": self.sound93},
                    94: {"type": "key", "value": 'u', "audio": self.sound94},
                    95: {"type": "key", "value": 'u', "audio": self.sound95}
                }
            }

    def mn1p(self):
        self.sound084.play()
    def mn2p(self):
        self.sound086.play()
    def mn3p(self):
        self.sound088.play()
    def mn4p(self):
        self.sound089.play()
    def mn5p(self):
        self.sound091.play()
    def mn6p(self):
        self.sound093.play()
    def mn7p(self):
        self.sound095.play()
    def mn8p(self):
        self.sound072.play()
    def mn9p(self):
        self.sound074.play()
    def mn10p(self):
        self.sound076.play()
    def mn11p(self):
        self.sound077.play()
    def mn12p(self):
        self.sound079.play()
    def mn13p(self):
        self.sound081.play()
    def mn14p(self):
        self.sound083.play()
    def mn15p(self):
        self.sound060.play()
    def mn16p(self):
        self.sound062.play()
    def mn17p(self):
        self.sound064.play()
    def mn18p(self):
        self.sound065.play()
    def mn19p(self):
        self.sound067.play()
    def mn20p(self):
        self.sound069.play()
    def mn21p(self):
        self.sound071.play()
    def mn22p(self):
        self.sound048.play()
    def mn23p(self):
        self.sound050.play()
    def mn24p(self):
        self.sound052.play()
    def mn25p(self):
        self.sound053.play()
    def mn26p(self):
        self.sound055.play()
    def mn27p(self):
        self.sound057.play()
    def mn28p(self):
        self.sound059.play()
    def mn29p(self):
        self.sound036.play()
    def mn30p(self):
        self.sound038.play()
    def mn31p(self):
        self.sound040.play()
    def mn32p(self):
        self.sound041.play()
    def mn33p(self):
        self.sound043.play()
    def mn34p(self):
        self.sound045.play()
    def mn35p(self):
        self.sound047.play()
    def mn36p(self):
        self.sound085.play()
    def mn37p(self):
        self.sound087.play()
    def mn38p(self):
        self.sound090.play()
    def mn39p(self):
        self.sound092.play()
    def mn40p(self):
        self.sound094.play()
    def mn41p(self):
        self.sound073.play()
    def mn42p(self):
        self.sound075.play()
    def mn43p(self):
        self.sound078.play()
    def mn44p(self):
        self.sound080.play()
    def mn45p(self):
        self.sound082.play()
    def mn46p(self):
        self.sound061.play()
    def mn47p(self):
        self.sound063.play()
    def mn48p(self):
        self.sound066.play()
    def mn49p(self):
        self.sound068.play()
    def mn50p(self):
        self.sound070.play()
    def mn51p(self):
        self.sound049.play()
    def mn52p(self):
        self.sound051.play()
    def mn53p(self):
        self.sound054.play()
    def mn54p(self):
        self.sound056.play()
    def mn55p(self):
        self.sound058.play()
    def mn56p(self):
        self.sound037.play()
    def mn57p(self):
        self.sound039.play()
    def mn58p(self):
        self.sound042.play()
    def mn59p(self):
        self.sound044.play()
    def mn60p(self):
        self.sound046.play()
    
    def mn75p(self, index):
        if index == 0:
            self.mn_listener = 1
            self.sound0f.play()
            try:
                self.sound036 = pygame.mixer.Sound(r'resource\Windsong_Lyre\,.wav')
                self.sound037 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#,.wav')
                self.sound038 = pygame.mixer.Sound(r'resource\Windsong_Lyre\..wav')
                self.sound039 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#..wav')
                self.sound040 = pygame.mixer.Sound(r'resource\Windsong_Lyre\xie.wav')
                self.sound041 = pygame.mixer.Sound(r'resource\Windsong_Lyre\;.wav')
                self.sound042 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#;.wav')
                self.sound043 = pygame.mixer.Sound(r'resource\Windsong_Lyre\'.wav')
                self.sound044 = pygame.mixer.Sound('resource\\Windsong_Lyre\\#\'.wav')
                self.sound045 = pygame.mixer.Sound(r'resource\Windsong_Lyre\[.wav')
                self.sound046 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#[.wav')
                self.sound047 = pygame.mixer.Sound(r'resource\Windsong_Lyre\].wav')
                self.sound048 = pygame.mixer.Sound(r'resource\Windsong_Lyre\Z.wav')
                self.sound049 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Z.wav')
                self.sound050 = pygame.mixer.Sound(r'resource\Windsong_Lyre\X.wav')
                self.sound051 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#X.wav')
                self.sound052 = pygame.mixer.Sound(r'resource\Windsong_Lyre\C.wav')
                self.sound053 = pygame.mixer.Sound(r'resource\Windsong_Lyre\V.wav')
                self.sound054 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#V.wav')
                self.sound055 = pygame.mixer.Sound(r'resource\Windsong_Lyre\B.wav')
                self.sound056 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#B.wav')
                self.sound057 = pygame.mixer.Sound(r'resource\Windsong_Lyre\N.wav')
                self.sound058 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#N.wav')
                self.sound059 = pygame.mixer.Sound(r'resource\Windsong_Lyre\M.wav')
                self.sound060 = pygame.mixer.Sound(r'resource\Windsong_Lyre\A.wav')
                self.sound061 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#A.wav')
                self.sound062 = pygame.mixer.Sound(r'resource\Windsong_Lyre\S.wav')
                self.sound063 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#S.wav')
                self.sound064 = pygame.mixer.Sound(r'resource\Windsong_Lyre\D.wav')
                self.sound065 = pygame.mixer.Sound(r'resource\Windsong_Lyre\F.wav')
                self.sound066 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#F.wav')
                self.sound067 = pygame.mixer.Sound(r'resource\Windsong_Lyre\G.wav')
                self.sound068 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#G.wav')
                self.sound069 = pygame.mixer.Sound(r'resource\Windsong_Lyre\H.wav')
                self.sound070 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#H.wav')
                self.sound071 = pygame.mixer.Sound(r'resource\Windsong_Lyre\J.wav')
                self.sound072 = pygame.mixer.Sound(r'resource\Windsong_Lyre\Q.wav')
                self.sound073 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Q.wav')
                self.sound074 = pygame.mixer.Sound(r'resource\Windsong_Lyre\W.wav')
                self.sound075 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#W.wav')
                self.sound076 = pygame.mixer.Sound(r'resource\Windsong_Lyre\E.wav')
                self.sound077 = pygame.mixer.Sound(r'resource\Windsong_Lyre\R.wav')
                self.sound078 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#R.wav')
                self.sound079 = pygame.mixer.Sound(r'resource\Windsong_Lyre\T.wav')
                self.sound080 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#T.wav')
                self.sound081 = pygame.mixer.Sound(r'resource\Windsong_Lyre\Y.wav')
                self.sound082 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#Y.wav')
                self.sound083 = pygame.mixer.Sound(r'resource\Windsong_Lyre\U.wav')
                self.sound084 = pygame.mixer.Sound(r'resource\Windsong_Lyre\1.wav')
                self.sound085 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#1.wav')
                self.sound086 = pygame.mixer.Sound(r'resource\Windsong_Lyre\2.wav')
                self.sound087 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#2.wav')
                self.sound088 = pygame.mixer.Sound(r'resource\Windsong_Lyre\3.wav')
                self.sound089 = pygame.mixer.Sound(r'resource\Windsong_Lyre\4.wav')
                self.sound090 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#4.wav')
                self.sound091 = pygame.mixer.Sound(r'resource\Windsong_Lyre\5.wav')
                self.sound092 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#5.wav')
                self.sound093 = pygame.mixer.Sound(r'resource\Windsong_Lyre\6.wav')
                self.sound094 = pygame.mixer.Sound(r'resource\Windsong_Lyre\#6.wav')
                self.sound095 = pygame.mixer.Sound(r'resource\Windsong_Lyre\7.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.mn41.move(388, 387)
            self.mn42.move(513, 387)
            self.mn44.move(888, 387)
            self.mn45.move(1013, 387)
            self.mn47.move(513, 489)
            self.mn50.move(1013, 489)
            self.mn52.move(513, 591)
            self.mn55.move(1013, 591)
            self.mn1.setHidden(False)
            self.mn2.setHidden(False)
            self.mn3.setHidden(False)
            self.mn4.setHidden(False)
            self.mn5.setHidden(False)
            self.mn6.setHidden(False)
            self.mn7.setHidden(False)
            self.mn8.setHidden(False)
            self.mn9.setHidden(False)
            self.mn10.setHidden(False)
            self.mn11.setHidden(False)
            self.mn12.setHidden(False)
            self.mn13.setHidden(False)
            self.mn14.setHidden(False)
            self.mn15.setHidden(False)
            self.mn16.setHidden(False)
            self.mn17.setHidden(False)
            self.mn18.setHidden(False)
            self.mn19.setHidden(False)
            self.mn20.setHidden(False)
            self.mn21.setHidden(False)
            self.mn22.setHidden(False)
            self.mn23.setHidden(False)
            self.mn24.setHidden(False)
            self.mn25.setHidden(False)
            self.mn26.setHidden(False)
            self.mn27.setHidden(False)
            self.mn28.setHidden(False)
            self.mn29.setHidden(False)
            self.mn30.setHidden(False)
            self.mn31.setHidden(False)
            self.mn32.setHidden(False)
            self.mn33.setHidden(False)
            self.mn34.setHidden(False)
            self.mn35.setHidden(False)
            self.mn36.setHidden(False)
            self.mn37.setHidden(False)
            self.mn38.setHidden(False)
            self.mn39.setHidden(False)
            self.mn40.setHidden(False)
            self.mn41.setHidden(False)
            self.mn42.setHidden(False)
            self.mn43.setHidden(False)
            self.mn44.setHidden(False)
            self.mn45.setHidden(False)
            self.mn46.setHidden(False)
            self.mn47.setHidden(False)
            self.mn48.setHidden(False)
            self.mn49.setHidden(False)
            self.mn50.setHidden(False)
            self.mn51.setHidden(False)
            self.mn52.setHidden(False)
            self.mn53.setHidden(False)
            self.mn54.setHidden(False)
            self.mn55.setHidden(False)
            self.mn56.setHidden(False)
            self.mn57.setHidden(False)
            self.mn58.setHidden(False)
            self.mn59.setHidden(False)
            self.mn60.setHidden(False)
            self.mn61.setHidden(True)
            self.mn62.setHidden(True)
            self.mn63.setHidden(True)
            self.mn64.setHidden(True)
            self.mn65.setHidden(True)
            self.mn66.setHidden(True)
            self.mn67.setHidden(True)
            self.mn68.setHidden(True)
            self.mn69.setHidden(True)
            self.mn70.setHidden(True)
            self.mn71.setHidden(True)
            self.mn72.setHidden(True)
            self.mn73.setHidden(True)
            self.mn74.setHidden(True)
            self.mn8.setIcon(QIcon(r'resource\Windsong_Lyre\fQ.png'))
            self.mn8.setIconSize(QSize(80, 80))
            self.mn9.setIcon(QIcon(r'resource\Windsong_Lyre\fW.png'))
            self.mn9.setIconSize(QSize(80, 80))
            self.mn10.setIcon(QIcon(r'resource\Windsong_Lyre\fE.png'))
            self.mn10.setIconSize(QSize(80, 80))
            self.mn11.setIcon(QIcon(r'resource\Windsong_Lyre\fR.png'))
            self.mn11.setIconSize(QSize(80, 80))
            self.mn12.setIcon(QIcon(r'resource\Windsong_Lyre\fT.png'))
            self.mn12.setIconSize(QSize(80, 80))
            self.mn13.setIcon(QIcon(r'resource\Windsong_Lyre\fY.png'))
            self.mn13.setIconSize(QSize(80, 80))
            self.mn14.setIcon(QIcon(r'resource\Windsong_Lyre\fU.png'))
            self.mn14.setIconSize(QSize(80, 80))
            self.mn15.setIcon(QIcon(r'resource\Windsong_Lyre\fQ.png'))
            self.mn15.setIconSize(QSize(80, 80))
            self.mn16.setIcon(QIcon(r'resource\Windsong_Lyre\fW.png'))
            self.mn16.setIconSize(QSize(80, 80))
            self.mn17.setIcon(QIcon(r'resource\Windsong_Lyre\fE.png'))
            self.mn17.setIconSize(QSize(80, 80))
            self.mn18.setIcon(QIcon(r'resource\Windsong_Lyre\fR.png'))
            self.mn18.setIconSize(QSize(80, 80))
            self.mn19.setIcon(QIcon(r'resource\Windsong_Lyre\fT.png'))
            self.mn19.setIconSize(QSize(80, 80))
            self.mn20.setIcon(QIcon(r'resource\Windsong_Lyre\fY.png'))
            self.mn20.setIconSize(QSize(80, 80))
            self.mn21.setIcon(QIcon(r'resource\Windsong_Lyre\fU.png'))
            self.mn21.setIconSize(QSize(80, 80))
            self.mn22.setIcon(QIcon(r'resource\Windsong_Lyre\fQ.png'))
            self.mn22.setIconSize(QSize(80, 80))
            self.mn23.setIcon(QIcon(r'resource\Windsong_Lyre\fW.png'))
            self.mn23.setIconSize(QSize(80, 80))
            self.mn24.setIcon(QIcon(r'resource\Windsong_Lyre\fE.png'))
            self.mn24.setIconSize(QSize(80, 80))
            self.mn25.setIcon(QIcon(r'resource\Windsong_Lyre\fR.png'))
            self.mn25.setIconSize(QSize(80, 80))
            self.mn26.setIcon(QIcon(r'resource\Windsong_Lyre\fT.png'))
            self.mn26.setIconSize(QSize(80, 80))
            self.mn27.setIcon(QIcon(r'resource\Windsong_Lyre\fY.png'))
            self.mn27.setIconSize(QSize(80, 80))
            self.mn28.setIcon(QIcon(r'resource\Windsong_Lyre\fU.png'))
            self.mn28.setIconSize(QSize(80, 80))

        if index == 1:
            self.mn_listener = 2
            self.sound0j.play()
            try:
                self.sound036 = pygame.mixer.Sound(r'resource\Floral_Zither\,.wav')
                self.sound037 = pygame.mixer.Sound(r'resource\Floral_Zither\#,.wav')
                self.sound038 = pygame.mixer.Sound(r'resource\Floral_Zither\..wav')
                self.sound039 = pygame.mixer.Sound(r'resource\Floral_Zither\#..wav')
                self.sound040 = pygame.mixer.Sound(r'resource\Floral_Zither\xie.wav')
                self.sound041 = pygame.mixer.Sound(r'resource\Floral_Zither\;.wav')
                self.sound042 = pygame.mixer.Sound(r'resource\Floral_Zither\#;.wav')
                self.sound043 = pygame.mixer.Sound(r'resource\Floral_Zither\'.wav')
                self.sound044 = pygame.mixer.Sound('resource\\Floral_Zither\\#\'.wav')
                self.sound045 = pygame.mixer.Sound(r'resource\Floral_Zither\[.wav')
                self.sound046 = pygame.mixer.Sound(r'resource\Floral_Zither\#[.wav')
                self.sound047 = pygame.mixer.Sound(r'resource\Floral_Zither\].wav')
                self.sound048 = pygame.mixer.Sound(r'resource\Floral_Zither\Z.wav')
                self.sound049 = pygame.mixer.Sound(r'resource\Floral_Zither\#Z.wav')
                self.sound050 = pygame.mixer.Sound(r'resource\Floral_Zither\X.wav')
                self.sound051 = pygame.mixer.Sound(r'resource\Floral_Zither\#X.wav')
                self.sound052 = pygame.mixer.Sound(r'resource\Floral_Zither\C.wav')
                self.sound053 = pygame.mixer.Sound(r'resource\Floral_Zither\V.wav')
                self.sound054 = pygame.mixer.Sound(r'resource\Floral_Zither\#V.wav')
                self.sound055 = pygame.mixer.Sound(r'resource\Floral_Zither\B.wav')
                self.sound056 = pygame.mixer.Sound(r'resource\Floral_Zither\#B.wav')
                self.sound057 = pygame.mixer.Sound(r'resource\Floral_Zither\N.wav')
                self.sound058 = pygame.mixer.Sound(r'resource\Floral_Zither\#N.wav')
                self.sound059 = pygame.mixer.Sound(r'resource\Floral_Zither\M.wav')
                self.sound060 = pygame.mixer.Sound(r'resource\Floral_Zither\A.wav')
                self.sound061 = pygame.mixer.Sound(r'resource\Floral_Zither\#A.wav')
                self.sound062 = pygame.mixer.Sound(r'resource\Floral_Zither\S.wav')
                self.sound063 = pygame.mixer.Sound(r'resource\Floral_Zither\#S.wav')
                self.sound064 = pygame.mixer.Sound(r'resource\Floral_Zither\D.wav')
                self.sound065 = pygame.mixer.Sound(r'resource\Floral_Zither\F.wav')
                self.sound066 = pygame.mixer.Sound(r'resource\Floral_Zither\#F.wav')
                self.sound067 = pygame.mixer.Sound(r'resource\Floral_Zither\G.wav')
                self.sound068 = pygame.mixer.Sound(r'resource\Floral_Zither\#G.wav')
                self.sound069 = pygame.mixer.Sound(r'resource\Floral_Zither\H.wav')
                self.sound070 = pygame.mixer.Sound(r'resource\Floral_Zither\#H.wav')
                self.sound071 = pygame.mixer.Sound(r'resource\Floral_Zither\J.wav')
                self.sound072 = pygame.mixer.Sound(r'resource\Floral_Zither\Q.wav')
                self.sound073 = pygame.mixer.Sound(r'resource\Floral_Zither\#Q.wav')
                self.sound074 = pygame.mixer.Sound(r'resource\Floral_Zither\W.wav')
                self.sound075 = pygame.mixer.Sound(r'resource\Floral_Zither\#W.wav')
                self.sound076 = pygame.mixer.Sound(r'resource\Floral_Zither\E.wav')
                self.sound077 = pygame.mixer.Sound(r'resource\Floral_Zither\R.wav')
                self.sound078 = pygame.mixer.Sound(r'resource\Floral_Zither\#R.wav')
                self.sound079 = pygame.mixer.Sound(r'resource\Floral_Zither\T.wav')
                self.sound080 = pygame.mixer.Sound(r'resource\Floral_Zither\#T.wav')
                self.sound081 = pygame.mixer.Sound(r'resource\Floral_Zither\Y.wav')
                self.sound082 = pygame.mixer.Sound(r'resource\Floral_Zither\#Y.wav')
                self.sound083 = pygame.mixer.Sound(r'resource\Floral_Zither\U.wav')
                self.sound084 = pygame.mixer.Sound(r'resource\Floral_Zither\1.wav')
                self.sound085 = pygame.mixer.Sound(r'resource\Floral_Zither\#1.wav')
                self.sound086 = pygame.mixer.Sound(r'resource\Floral_Zither\2.wav')
                self.sound087 = pygame.mixer.Sound(r'resource\Floral_Zither\#2.wav')
                self.sound088 = pygame.mixer.Sound(r'resource\Floral_Zither\3.wav')
                self.sound089 = pygame.mixer.Sound(r'resource\Floral_Zither\4.wav')
                self.sound090 = pygame.mixer.Sound(r'resource\Floral_Zither\#4.wav')
                self.sound091 = pygame.mixer.Sound(r'resource\Floral_Zither\5.wav')
                self.sound092 = pygame.mixer.Sound(r'resource\Floral_Zither\#5.wav')
                self.sound093 = pygame.mixer.Sound(r'resource\Floral_Zither\6.wav')
                self.sound094 = pygame.mixer.Sound(r'resource\Floral_Zither\#6.wav')
                self.sound095 = pygame.mixer.Sound(r'resource\Floral_Zither\7.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.mn41.move(388, 387)
            self.mn42.move(513, 387)
            self.mn44.move(888, 387)
            self.mn45.move(1013, 387)
            self.mn47.move(513, 489)
            self.mn50.move(1013, 489)
            self.mn52.move(513, 591)
            self.mn55.move(1013, 591)
            self.mn1.setHidden(False)
            self.mn2.setHidden(False)
            self.mn3.setHidden(False)
            self.mn4.setHidden(False)
            self.mn5.setHidden(False)
            self.mn6.setHidden(False)
            self.mn7.setHidden(False)
            self.mn8.setHidden(False)
            self.mn9.setHidden(False)
            self.mn10.setHidden(False)
            self.mn11.setHidden(False)
            self.mn12.setHidden(False)
            self.mn13.setHidden(False)
            self.mn14.setHidden(False)
            self.mn15.setHidden(False)
            self.mn16.setHidden(False)
            self.mn17.setHidden(False)
            self.mn18.setHidden(False)
            self.mn19.setHidden(False)
            self.mn20.setHidden(False)
            self.mn21.setHidden(False)
            self.mn22.setHidden(False)
            self.mn23.setHidden(False)
            self.mn24.setHidden(False)
            self.mn25.setHidden(False)
            self.mn26.setHidden(False)
            self.mn27.setHidden(False)
            self.mn28.setHidden(False)
            self.mn29.setHidden(False)
            self.mn30.setHidden(False)
            self.mn31.setHidden(False)
            self.mn32.setHidden(False)
            self.mn33.setHidden(False)
            self.mn34.setHidden(False)
            self.mn35.setHidden(False)
            self.mn36.setHidden(False)
            self.mn37.setHidden(False)
            self.mn38.setHidden(False)
            self.mn39.setHidden(False)
            self.mn40.setHidden(False)
            self.mn41.setHidden(False)
            self.mn42.setHidden(False)
            self.mn43.setHidden(False)
            self.mn44.setHidden(False)
            self.mn45.setHidden(False)
            self.mn46.setHidden(False)
            self.mn47.setHidden(False)
            self.mn48.setHidden(False)
            self.mn49.setHidden(False)
            self.mn50.setHidden(False)
            self.mn51.setHidden(False)
            self.mn52.setHidden(False)
            self.mn53.setHidden(False)
            self.mn54.setHidden(False)
            self.mn55.setHidden(False)
            self.mn56.setHidden(False)
            self.mn57.setHidden(False)
            self.mn58.setHidden(False)
            self.mn59.setHidden(False)
            self.mn60.setHidden(False)
            self.mn61.setHidden(True)
            self.mn62.setHidden(True)
            self.mn63.setHidden(True)
            self.mn64.setHidden(True)
            self.mn65.setHidden(True)
            self.mn66.setHidden(True)
            self.mn67.setHidden(True)
            self.mn68.setHidden(True)
            self.mn69.setHidden(True)
            self.mn70.setHidden(True)
            self.mn71.setHidden(True)
            self.mn72.setHidden(True)
            self.mn73.setHidden(True)
            self.mn74.setHidden(True)
            self.mn8.setIcon(QIcon(r'resource\Floral_Zither\jQ.png'))
            self.mn8.setIconSize(QSize(80, 80))
            self.mn9.setIcon(QIcon(r'resource\Floral_Zither\jW.png'))
            self.mn9.setIconSize(QSize(80, 80))
            self.mn10.setIcon(QIcon(r'resource\Floral_Zither\jE.png'))
            self.mn10.setIconSize(QSize(80, 80))
            self.mn11.setIcon(QIcon(r'resource\Floral_Zither\jR.png'))
            self.mn11.setIconSize(QSize(80, 80))
            self.mn12.setIcon(QIcon(r'resource\Floral_Zither\jT.png'))
            self.mn12.setIconSize(QSize(80, 80))
            self.mn13.setIcon(QIcon(r'resource\Floral_Zither\jY.png'))
            self.mn13.setIconSize(QSize(80, 80))
            self.mn14.setIcon(QIcon(r'resource\Floral_Zither\jU.png'))
            self.mn14.setIconSize(QSize(80, 80))
            self.mn15.setIcon(QIcon(r'resource\Floral_Zither\jQ.png'))
            self.mn15.setIconSize(QSize(80, 80))
            self.mn16.setIcon(QIcon(r'resource\Floral_Zither\jW.png'))
            self.mn16.setIconSize(QSize(80, 80))
            self.mn17.setIcon(QIcon(r'resource\Floral_Zither\jE.png'))
            self.mn17.setIconSize(QSize(80, 80))
            self.mn18.setIcon(QIcon(r'resource\Floral_Zither\jR.png'))
            self.mn18.setIconSize(QSize(80, 80))
            self.mn19.setIcon(QIcon(r'resource\Floral_Zither\jT.png'))
            self.mn19.setIconSize(QSize(80, 80))
            self.mn20.setIcon(QIcon(r'resource\Floral_Zither\jY.png'))
            self.mn20.setIconSize(QSize(80, 80))
            self.mn21.setIcon(QIcon(r'resource\Floral_Zither\jU.png'))
            self.mn21.setIconSize(QSize(80, 80))
            self.mn22.setIcon(QIcon(r'resource\Floral_Zither\jQ.png'))
            self.mn22.setIconSize(QSize(80, 80))
            self.mn23.setIcon(QIcon(r'resource\Floral_Zither\jW.png'))
            self.mn23.setIconSize(QSize(80, 80))
            self.mn24.setIcon(QIcon(r'resource\Floral_Zither\jE.png'))
            self.mn24.setIconSize(QSize(80, 80))
            self.mn25.setIcon(QIcon(r'resource\Floral_Zither\jR.png'))
            self.mn25.setIconSize(QSize(80, 80))
            self.mn26.setIcon(QIcon(r'resource\Floral_Zither\jT.png'))
            self.mn26.setIconSize(QSize(80, 80))
            self.mn27.setIcon(QIcon(r'resource\Floral_Zither\jY.png'))
            self.mn27.setIconSize(QSize(80, 80))
            self.mn28.setIcon(QIcon(r'resource\Floral_Zither\jU.png'))
            self.mn28.setIconSize(QSize(80, 80))

        if index == 3:
            self.mn_listener = 4
            self.sound0l.play()
            try:
                self.sound036 = pygame.mixer.Sound(r'resource\Vintage_Lyre\,.wav')
                self.sound037 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#,.wav')
                self.sound038 = pygame.mixer.Sound(r'resource\Vintage_Lyre\..wav')
                self.sound039 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#..wav')
                self.sound040 = pygame.mixer.Sound(r'resource\Vintage_Lyre\xie.wav')
                self.sound041 = pygame.mixer.Sound(r'resource\Vintage_Lyre\;.wav')
                self.sound042 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#;.wav')
                self.sound043 = pygame.mixer.Sound(r'resource\Vintage_Lyre\'.wav')
                self.sound044 = pygame.mixer.Sound('resource\\Vintage_Lyre\\#\'.wav')
                self.sound045 = pygame.mixer.Sound(r'resource\Vintage_Lyre\[.wav')
                self.sound046 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#[.wav')
                self.sound047 = pygame.mixer.Sound(r'resource\Vintage_Lyre\].wav')
                self.sound048 = pygame.mixer.Sound(r'resource\Vintage_Lyre\Z.wav')
                self.sound049 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#Z.wav')
                self.sound050 = pygame.mixer.Sound(r'resource\Vintage_Lyre\X.wav')
                self.sound051 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#C.wav')
                self.sound052 = pygame.mixer.Sound(r'resource\Vintage_Lyre\C.wav')
                self.sound053 = pygame.mixer.Sound(r'resource\Vintage_Lyre\V.wav')
                self.sound054 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#V.wav')
                self.sound055 = pygame.mixer.Sound(r'resource\Vintage_Lyre\B.wav')
                self.sound056 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#B.wav')
                self.sound057 = pygame.mixer.Sound(r'resource\Vintage_Lyre\N.wav')
                self.sound058 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#M.wav')
                self.sound059 = pygame.mixer.Sound(r'resource\Vintage_Lyre\M.wav')
                self.sound060 = pygame.mixer.Sound(r'resource\Vintage_Lyre\A.wav')
                self.sound061 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#A.wav')
                self.sound062 = pygame.mixer.Sound(r'resource\Vintage_Lyre\S.wav')
                self.sound063 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#D.wav')
                self.sound064 = pygame.mixer.Sound(r'resource\Vintage_Lyre\D.wav')
                self.sound065 = pygame.mixer.Sound(r'resource\Vintage_Lyre\F.wav')
                self.sound066 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#F.wav')
                self.sound067 = pygame.mixer.Sound(r'resource\Vintage_Lyre\G.wav')
                self.sound068 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#G.wav')
                self.sound069 = pygame.mixer.Sound(r'resource\Vintage_Lyre\H.wav')
                self.sound070 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#J.wav')
                self.sound071 = pygame.mixer.Sound(r'resource\Vintage_Lyre\J.wav')
                self.sound072 = pygame.mixer.Sound(r'resource\Vintage_Lyre\Q.wav')
                self.sound073 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#W.wav')
                self.sound074 = pygame.mixer.Sound(r'resource\Vintage_Lyre\W.wav')
                self.sound075 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#E.wav')
                self.sound076 = pygame.mixer.Sound(r'resource\Vintage_Lyre\E.wav')
                self.sound077 = pygame.mixer.Sound(r'resource\Vintage_Lyre\R.wav')
                self.sound078 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#R.wav')
                self.sound079 = pygame.mixer.Sound(r'resource\Vintage_Lyre\T.wav')
                self.sound080 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#Y.wav')
                self.sound081 = pygame.mixer.Sound(r'resource\Vintage_Lyre\Y.wav')
                self.sound082 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#U.wav')
                self.sound083 = pygame.mixer.Sound(r'resource\Vintage_Lyre\U.wav')
                self.sound084 = pygame.mixer.Sound(r'resource\Vintage_Lyre\1.wav')
                self.sound085 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#1.wav')
                self.sound086 = pygame.mixer.Sound(r'resource\Vintage_Lyre\2.wav')
                self.sound087 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#2.wav')
                self.sound088 = pygame.mixer.Sound(r'resource\Vintage_Lyre\3.wav')
                self.sound089 = pygame.mixer.Sound(r'resource\Vintage_Lyre\4.wav')
                self.sound090 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#4.wav')
                self.sound091 = pygame.mixer.Sound(r'resource\Vintage_Lyre\5.wav')
                self.sound092 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#5.wav')
                self.sound093 = pygame.mixer.Sound(r'resource\Vintage_Lyre\6.wav')
                self.sound094 = pygame.mixer.Sound(r'resource\Vintage_Lyre\#6.wav')
                self.sound095 = pygame.mixer.Sound(r'resource\Vintage_Lyre\7.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.mn41.move(513, 387)
            self.mn42.move(638, 387)
            self.mn44.move(1013, 387)
            self.mn45.move(1138, 387)
            self.mn47.move(638, 489)
            self.mn50.move(1138, 489)
            self.mn52.move(638, 591)
            self.mn55.move(1138, 591)
            self.mn1.setHidden(False)
            self.mn2.setHidden(False)
            self.mn3.setHidden(False)
            self.mn4.setHidden(False)
            self.mn5.setHidden(False)
            self.mn6.setHidden(False)
            self.mn7.setHidden(False)
            self.mn8.setHidden(False)
            self.mn9.setHidden(False)
            self.mn10.setHidden(False)
            self.mn11.setHidden(False)
            self.mn12.setHidden(False)
            self.mn13.setHidden(False)
            self.mn14.setHidden(False)
            self.mn15.setHidden(False)
            self.mn16.setHidden(False)
            self.mn17.setHidden(False)
            self.mn18.setHidden(False)
            self.mn19.setHidden(False)
            self.mn20.setHidden(False)
            self.mn21.setHidden(False)
            self.mn22.setHidden(False)
            self.mn23.setHidden(False)
            self.mn24.setHidden(False)
            self.mn25.setHidden(False)
            self.mn26.setHidden(False)
            self.mn27.setHidden(False)
            self.mn28.setHidden(False)
            self.mn29.setHidden(False)
            self.mn30.setHidden(False)
            self.mn31.setHidden(False)
            self.mn32.setHidden(False)
            self.mn33.setHidden(False)
            self.mn34.setHidden(False)
            self.mn35.setHidden(False)
            self.mn36.setHidden(False)
            self.mn37.setHidden(False)
            self.mn38.setHidden(False)
            self.mn39.setHidden(False)
            self.mn40.setHidden(False)
            self.mn41.setHidden(False)
            self.mn42.setHidden(False)
            self.mn43.setHidden(False)
            self.mn44.setHidden(False)
            self.mn45.setHidden(False)
            self.mn46.setHidden(False)
            self.mn47.setHidden(False)
            self.mn48.setHidden(False)
            self.mn49.setHidden(False)
            self.mn50.setHidden(False)
            self.mn51.setHidden(False)
            self.mn52.setHidden(False)
            self.mn53.setHidden(False)
            self.mn54.setHidden(False)
            self.mn55.setHidden(False)
            self.mn56.setHidden(False)
            self.mn57.setHidden(False)
            self.mn58.setHidden(False)
            self.mn59.setHidden(False)
            self.mn60.setHidden(False)
            self.mn61.setHidden(True)
            self.mn62.setHidden(True)
            self.mn63.setHidden(True)
            self.mn64.setHidden(True)
            self.mn65.setHidden(True)
            self.mn66.setHidden(True)
            self.mn67.setHidden(True)
            self.mn68.setHidden(True)
            self.mn69.setHidden(True)
            self.mn70.setHidden(True)
            self.mn71.setHidden(True)
            self.mn72.setHidden(True)
            self.mn73.setHidden(True)
            self.mn74.setHidden(True)
            self.mn8.setIcon(QIcon(r'resource\Vintage_Lyre\lQ.png'))
            self.mn8.setIconSize(QSize(80, 80))
            self.mn9.setIcon(QIcon(r'resource\Vintage_Lyre\lW.png'))
            self.mn9.setIconSize(QSize(80, 80))
            self.mn10.setIcon(QIcon(r'resource\Vintage_Lyre\lE.png'))
            self.mn10.setIconSize(QSize(80, 80))
            self.mn11.setIcon(QIcon(r'resource\Vintage_Lyre\lR.png'))
            self.mn11.setIconSize(QSize(80, 80))
            self.mn12.setIcon(QIcon(r'resource\Vintage_Lyre\lT.png'))
            self.mn12.setIconSize(QSize(80, 80))
            self.mn13.setIcon(QIcon(r'resource\Vintage_Lyre\lY.png'))
            self.mn13.setIconSize(QSize(80, 80))
            self.mn14.setIcon(QIcon(r'resource\Vintage_Lyre\lU.png'))
            self.mn14.setIconSize(QSize(80, 80))
            self.mn15.setIcon(QIcon(r'resource\Vintage_Lyre\lQ.png'))
            self.mn15.setIconSize(QSize(80, 80))
            self.mn16.setIcon(QIcon(r'resource\Vintage_Lyre\lS.png'))
            self.mn16.setIconSize(QSize(80, 80))
            self.mn17.setIcon(QIcon(r'resource\Vintage_Lyre\lE.png'))
            self.mn17.setIconSize(QSize(80, 80))
            self.mn18.setIcon(QIcon(r'resource\Vintage_Lyre\lR.png'))
            self.mn18.setIconSize(QSize(80, 80))
            self.mn19.setIcon(QIcon(r'resource\Vintage_Lyre\lT.png'))
            self.mn19.setIconSize(QSize(80, 80))
            self.mn20.setIcon(QIcon(r'resource\Vintage_Lyre\lH.png'))
            self.mn20.setIconSize(QSize(80, 80))
            self.mn21.setIcon(QIcon(r'resource\Vintage_Lyre\lU.png'))
            self.mn21.setIconSize(QSize(80, 80))
            self.mn22.setIcon(QIcon(r'resource\Vintage_Lyre\lQ.png'))
            self.mn22.setIconSize(QSize(80, 80))
            self.mn23.setIcon(QIcon(r'resource\Vintage_Lyre\lS.png'))
            self.mn23.setIconSize(QSize(80, 80))
            self.mn24.setIcon(QIcon(r'resource\Vintage_Lyre\lE.png'))
            self.mn24.setIconSize(QSize(80, 80))
            self.mn25.setIcon(QIcon(r'resource\Vintage_Lyre\lR.png'))
            self.mn25.setIconSize(QSize(80, 80))
            self.mn26.setIcon(QIcon(r'resource\Vintage_Lyre\lT.png'))
            self.mn26.setIconSize(QSize(80, 80))
            self.mn27.setIcon(QIcon(r'resource\Vintage_Lyre\lH.png'))
            self.mn27.setIconSize(QSize(80, 80))
            self.mn28.setIcon(QIcon(r'resource\Vintage_Lyre\lU.png'))
            self.mn28.setIconSize(QSize(80, 80))

        if index == 8:
            self.mn_listener = 9
            self.sound0y.play()
            try:
                self.sound036 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\,.wav')
                self.sound037 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#,.wav')
                self.sound038 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\..wav')
                self.sound039 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#..wav')
                self.sound040 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\xie.wav')
                self.sound041 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\;.wav')
                self.sound042 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#;.wav')
                self.sound043 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\'.wav')
                self.sound044 = pygame.mixer.Sound('resource\\Leaping_Spirit_Piano\\#\'.wav')
                self.sound045 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\[.wav')
                self.sound046 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#[.wav')
                self.sound047 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\].wav')
                self.sound048 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\Z.wav')
                self.sound049 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#Z.wav')
                self.sound050 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\X.wav')
                self.sound051 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#X.wav')
                self.sound052 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\C.wav')
                self.sound053 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\V.wav')
                self.sound054 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#V.wav')
                self.sound055 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\B.wav')
                self.sound056 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#B.wav')
                self.sound057 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\N.wav')
                self.sound058 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#N.wav')
                self.sound059 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\M.wav')
                self.sound060 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\A.wav')
                self.sound061 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#A.wav')
                self.sound062 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\S.wav')
                self.sound063 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#S.wav')
                self.sound064 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\D.wav')
                self.sound065 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\F.wav')
                self.sound066 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#F.wav')
                self.sound067 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\G.wav')
                self.sound068 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#G.wav')
                self.sound069 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\H.wav')
                self.sound070 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#H.wav')
                self.sound071 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\J.wav')
                self.sound072 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\Q.wav')
                self.sound073 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#Q.wav')
                self.sound074 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\W.wav')
                self.sound075 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#W.wav')
                self.sound076 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\E.wav')
                self.sound077 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\R.wav')
                self.sound078 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#R.wav')
                self.sound079 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\T.wav')
                self.sound080 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#T.wav')
                self.sound081 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\Y.wav')
                self.sound082 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#Y.wav')
                self.sound083 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\U.wav')
                self.sound084 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\1.wav')
                self.sound085 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#1.wav')
                self.sound086 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\2.wav')
                self.sound087 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#2.wav')
                self.sound088 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\3.wav')
                self.sound089 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\4.wav')
                self.sound090 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#4.wav')
                self.sound091 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\5.wav')
                self.sound092 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#5.wav')
                self.sound093 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\6.wav')
                self.sound094 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\#6.wav')
                self.sound095 = pygame.mixer.Sound(r'resource\Leaping_Spirit_Piano\7.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.mn41.move(388, 387)
            self.mn42.move(513, 387)
            self.mn44.move(888, 387)
            self.mn45.move(1013, 387)
            self.mn47.move(513, 489)
            self.mn50.move(1013, 489)
            self.mn52.move(513, 591)
            self.mn55.move(1013, 591)
            self.mn1.setHidden(False)
            self.mn2.setHidden(False)
            self.mn3.setHidden(False)
            self.mn4.setHidden(False)
            self.mn5.setHidden(False)
            self.mn6.setHidden(False)
            self.mn7.setHidden(False)
            self.mn8.setHidden(False)
            self.mn9.setHidden(False)
            self.mn10.setHidden(False)
            self.mn11.setHidden(False)
            self.mn12.setHidden(False)
            self.mn13.setHidden(False)
            self.mn14.setHidden(False)
            self.mn15.setHidden(False)
            self.mn16.setHidden(False)
            self.mn17.setHidden(False)
            self.mn18.setHidden(False)
            self.mn19.setHidden(False)
            self.mn20.setHidden(False)
            self.mn21.setHidden(False)
            self.mn22.setHidden(False)
            self.mn23.setHidden(False)
            self.mn24.setHidden(False)
            self.mn25.setHidden(False)
            self.mn26.setHidden(False)
            self.mn27.setHidden(False)
            self.mn28.setHidden(False)
            self.mn29.setHidden(False)
            self.mn30.setHidden(False)
            self.mn31.setHidden(False)
            self.mn32.setHidden(False)
            self.mn33.setHidden(False)
            self.mn34.setHidden(False)
            self.mn35.setHidden(False)
            self.mn36.setHidden(False)
            self.mn37.setHidden(False)
            self.mn38.setHidden(False)
            self.mn39.setHidden(False)
            self.mn40.setHidden(False)
            self.mn41.setHidden(False)
            self.mn42.setHidden(False)
            self.mn43.setHidden(False)
            self.mn44.setHidden(False)
            self.mn45.setHidden(False)
            self.mn46.setHidden(False)
            self.mn47.setHidden(False)
            self.mn48.setHidden(False)
            self.mn49.setHidden(False)
            self.mn50.setHidden(False)
            self.mn51.setHidden(False)
            self.mn52.setHidden(False)
            self.mn53.setHidden(False)
            self.mn54.setHidden(False)
            self.mn55.setHidden(False)
            self.mn56.setHidden(False)
            self.mn57.setHidden(False)
            self.mn58.setHidden(False)
            self.mn59.setHidden(False)
            self.mn60.setHidden(False)
            self.mn61.setHidden(True)
            self.mn62.setHidden(True)
            self.mn63.setHidden(True)
            self.mn64.setHidden(True)
            self.mn65.setHidden(True)
            self.mn66.setHidden(True)
            self.mn67.setHidden(True)
            self.mn68.setHidden(True)
            self.mn69.setHidden(True)
            self.mn70.setHidden(True)
            self.mn71.setHidden(True)
            self.mn72.setHidden(True)
            self.mn73.setHidden(True)
            self.mn74.setHidden(True)
            self.mn8.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yQ.png'))
            self.mn8.setIconSize(QSize(80, 80))
            self.mn9.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yW.png'))
            self.mn9.setIconSize(QSize(80, 80))
            self.mn10.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yE.png'))
            self.mn10.setIconSize(QSize(80, 80))
            self.mn11.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yR.png'))
            self.mn11.setIconSize(QSize(80, 80))
            self.mn12.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yT.png'))
            self.mn12.setIconSize(QSize(80, 80))
            self.mn13.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yY.png'))
            self.mn13.setIconSize(QSize(80, 80))
            self.mn14.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yU.png'))
            self.mn14.setIconSize(QSize(80, 80))
            self.mn15.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yQ.png'))
            self.mn15.setIconSize(QSize(80, 80))
            self.mn16.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yW.png'))
            self.mn16.setIconSize(QSize(80, 80))
            self.mn17.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yE.png'))
            self.mn17.setIconSize(QSize(80, 80))
            self.mn18.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yR.png'))
            self.mn18.setIconSize(QSize(80, 80))
            self.mn19.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yT.png'))
            self.mn19.setIconSize(QSize(80, 80))
            self.mn20.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yY.png'))
            self.mn20.setIconSize(QSize(80, 80))
            self.mn21.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yU.png'))
            self.mn21.setIconSize(QSize(80, 80))
            self.mn22.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yQ.png'))
            self.mn22.setIconSize(QSize(80, 80))
            self.mn23.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yW.png'))
            self.mn23.setIconSize(QSize(80, 80))
            self.mn24.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yE.png'))
            self.mn24.setIconSize(QSize(80, 80))
            self.mn25.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yR.png'))
            self.mn25.setIconSize(QSize(80, 80))
            self.mn26.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yT.png'))
            self.mn26.setIconSize(QSize(80, 80))
            self.mn27.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yY.png'))
            self.mn27.setIconSize(QSize(80, 80))
            self.mn28.setIcon(QIcon(r'resource\Leaping_Spirit_Piano\yU.png'))
            self.mn28.setIconSize(QSize(80, 80))

        if index == 9:
            self.mn_listener = 10
            try:
                self.sound036 = pygame.mixer.Sound(r'resource\Piano\,.wav')
                self.sound037 = pygame.mixer.Sound(r'resource\Piano\#,.wav')
                self.sound038 = pygame.mixer.Sound(r'resource\Piano\..wav')
                self.sound039 = pygame.mixer.Sound(r'resource\Piano\#..wav')
                self.sound040 = pygame.mixer.Sound(r'resource\Piano\xie.wav')
                self.sound041 = pygame.mixer.Sound(r'resource\Piano\;.wav')
                self.sound042 = pygame.mixer.Sound(r'resource\Piano\#;.wav')
                self.sound043 = pygame.mixer.Sound(r'resource\Piano\'.wav')
                self.sound044 = pygame.mixer.Sound('resource\\Piano\\#\'.wav')
                self.sound045 = pygame.mixer.Sound(r'resource\Piano\[.wav')
                self.sound046 = pygame.mixer.Sound(r'resource\Piano\#[.wav')
                self.sound047 = pygame.mixer.Sound(r'resource\Piano\].wav')
                self.sound048 = pygame.mixer.Sound(r'resource\Piano\Z.wav')
                self.sound049 = pygame.mixer.Sound(r'resource\Piano\#Z.wav')
                self.sound050 = pygame.mixer.Sound(r'resource\Piano\X.wav')
                self.sound051 = pygame.mixer.Sound(r'resource\Piano\#X.wav')
                self.sound052 = pygame.mixer.Sound(r'resource\Piano\C.wav')
                self.sound053 = pygame.mixer.Sound(r'resource\Piano\V.wav')
                self.sound054 = pygame.mixer.Sound(r'resource\Piano\#V.wav')
                self.sound055 = pygame.mixer.Sound(r'resource\Piano\B.wav')
                self.sound056 = pygame.mixer.Sound(r'resource\Piano\#B.wav')
                self.sound057 = pygame.mixer.Sound(r'resource\Piano\N.wav')
                self.sound058 = pygame.mixer.Sound(r'resource\Piano\#N.wav')
                self.sound059 = pygame.mixer.Sound(r'resource\Piano\M.wav')
                self.sound060 = pygame.mixer.Sound(r'resource\Piano\A.wav')
                self.sound061 = pygame.mixer.Sound(r'resource\Piano\#A.wav')
                self.sound062 = pygame.mixer.Sound(r'resource\Piano\S.wav')
                self.sound063 = pygame.mixer.Sound(r'resource\Piano\#S.wav')
                self.sound064 = pygame.mixer.Sound(r'resource\Piano\D.wav')
                self.sound065 = pygame.mixer.Sound(r'resource\Piano\F.wav')
                self.sound066 = pygame.mixer.Sound(r'resource\Piano\#F.wav')
                self.sound067 = pygame.mixer.Sound(r'resource\Piano\G.wav')
                self.sound068 = pygame.mixer.Sound(r'resource\Piano\#G.wav')
                self.sound069 = pygame.mixer.Sound(r'resource\Piano\H.wav')
                self.sound070 = pygame.mixer.Sound(r'resource\Piano\#H.wav')
                self.sound071 = pygame.mixer.Sound(r'resource\Piano\J.wav')
                self.sound072 = pygame.mixer.Sound(r'resource\Piano\Q.wav')
                self.sound073 = pygame.mixer.Sound(r'resource\Piano\#Q.wav')
                self.sound074 = pygame.mixer.Sound(r'resource\Piano\W.wav')
                self.sound075 = pygame.mixer.Sound(r'resource\Piano\#W.wav')
                self.sound076 = pygame.mixer.Sound(r'resource\Piano\E.wav')
                self.sound077 = pygame.mixer.Sound(r'resource\Piano\R.wav')
                self.sound078 = pygame.mixer.Sound(r'resource\Piano\#R.wav')
                self.sound079 = pygame.mixer.Sound(r'resource\Piano\T.wav')
                self.sound080 = pygame.mixer.Sound(r'resource\Piano\#T.wav')
                self.sound081 = pygame.mixer.Sound(r'resource\Piano\Y.wav')
                self.sound082 = pygame.mixer.Sound(r'resource\Piano\#Y.wav')
                self.sound083 = pygame.mixer.Sound(r'resource\Piano\U.wav')
                self.sound084 = pygame.mixer.Sound(r'resource\Piano\1.wav')
                self.sound085 = pygame.mixer.Sound(r'resource\Piano\#1.wav')
                self.sound086 = pygame.mixer.Sound(r'resource\Piano\2.wav')
                self.sound087 = pygame.mixer.Sound(r'resource\Piano\#2.wav')
                self.sound088 = pygame.mixer.Sound(r'resource\Piano\3.wav')
                self.sound089 = pygame.mixer.Sound(r'resource\Piano\4.wav')
                self.sound090 = pygame.mixer.Sound(r'resource\Piano\#4.wav')
                self.sound091 = pygame.mixer.Sound(r'resource\Piano\5.wav')
                self.sound092 = pygame.mixer.Sound(r'resource\Piano\#5.wav')
                self.sound093 = pygame.mixer.Sound(r'resource\Piano\6.wav')
                self.sound094 = pygame.mixer.Sound(r'resource\Piano\#6.wav')
                self.sound095 = pygame.mixer.Sound(r'resource\Piano\7.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.mn41.move(388, 387)
            self.mn42.move(513, 387)
            self.mn44.move(888, 387)
            self.mn45.move(1013, 387)
            self.mn47.move(513, 489)
            self.mn50.move(1013, 489)
            self.mn52.move(513, 591)
            self.mn55.move(1013, 591)
            self.mn1.setHidden(False)
            self.mn2.setHidden(False)
            self.mn3.setHidden(False)
            self.mn4.setHidden(False)
            self.mn5.setHidden(False)
            self.mn6.setHidden(False)
            self.mn7.setHidden(False)
            self.mn8.setHidden(False)
            self.mn9.setHidden(False)
            self.mn10.setHidden(False)
            self.mn11.setHidden(False)
            self.mn12.setHidden(False)
            self.mn13.setHidden(False)
            self.mn14.setHidden(False)
            self.mn15.setHidden(False)
            self.mn16.setHidden(False)
            self.mn17.setHidden(False)
            self.mn18.setHidden(False)
            self.mn19.setHidden(False)
            self.mn20.setHidden(False)
            self.mn21.setHidden(False)
            self.mn22.setHidden(False)
            self.mn23.setHidden(False)
            self.mn24.setHidden(False)
            self.mn25.setHidden(False)
            self.mn26.setHidden(False)
            self.mn27.setHidden(False)
            self.mn28.setHidden(False)
            self.mn29.setHidden(False)
            self.mn30.setHidden(False)
            self.mn31.setHidden(False)
            self.mn32.setHidden(False)
            self.mn33.setHidden(False)
            self.mn34.setHidden(False)
            self.mn35.setHidden(False)
            self.mn36.setHidden(False)
            self.mn37.setHidden(False)
            self.mn38.setHidden(False)
            self.mn39.setHidden(False)
            self.mn40.setHidden(False)
            self.mn41.setHidden(False)
            self.mn42.setHidden(False)
            self.mn43.setHidden(False)
            self.mn44.setHidden(False)
            self.mn45.setHidden(False)
            self.mn46.setHidden(False)
            self.mn47.setHidden(False)
            self.mn48.setHidden(False)
            self.mn49.setHidden(False)
            self.mn50.setHidden(False)
            self.mn51.setHidden(False)
            self.mn52.setHidden(False)
            self.mn53.setHidden(False)
            self.mn54.setHidden(False)
            self.mn55.setHidden(False)
            self.mn56.setHidden(False)
            self.mn57.setHidden(False)
            self.mn58.setHidden(False)
            self.mn59.setHidden(False)
            self.mn60.setHidden(False)
            self.mn61.setHidden(True)
            self.mn62.setHidden(True)
            self.mn63.setHidden(True)
            self.mn64.setHidden(True)
            self.mn65.setHidden(True)
            self.mn66.setHidden(True)
            self.mn67.setHidden(True)
            self.mn68.setHidden(True)
            self.mn69.setHidden(True)
            self.mn70.setHidden(True)
            self.mn71.setHidden(True)
            self.mn72.setHidden(True)
            self.mn73.setHidden(True)
            self.mn74.setHidden(True)

        if index == 5:
            self.mn_listener = 6
            self.sound0k.play()
            try:
                self.sound036 = pygame.mixer.Sound(r'resource\Ukulele\,.wav')
                self.sound037 = pygame.mixer.Sound(r'resource\Ukulele\#,.wav')
                self.sound038 = pygame.mixer.Sound(r'resource\Ukulele\..wav')
                self.sound039 = pygame.mixer.Sound(r'resource\Ukulele\#..wav')
                self.sound040 = pygame.mixer.Sound(r'resource\Ukulele\xie.wav')
                self.sound041 = pygame.mixer.Sound(r'resource\Ukulele\;.wav')
                self.sound042 = pygame.mixer.Sound(r'resource\Ukulele\#;.wav')
                self.sound043 = pygame.mixer.Sound(r'resource\Ukulele\'.wav')
                self.sound044 = pygame.mixer.Sound('resource\\Ukulele\\#\'.wav')
                self.sound045 = pygame.mixer.Sound(r'resource\Ukulele\[.wav')
                self.sound046 = pygame.mixer.Sound(r'resource\Ukulele\#[.wav')
                self.sound047 = pygame.mixer.Sound(r'resource\Ukulele\].wav')
                self.sound048 = pygame.mixer.Sound(r'resource\Ukulele\Z.wav')
                self.sound049 = pygame.mixer.Sound(r'resource\Ukulele\#Z.wav')
                self.sound050 = pygame.mixer.Sound(r'resource\Ukulele\X.wav')
                self.sound051 = pygame.mixer.Sound(r'resource\Ukulele\#X.wav')
                self.sound052 = pygame.mixer.Sound(r'resource\Ukulele\C.wav')
                self.sound053 = pygame.mixer.Sound(r'resource\Ukulele\V.wav')
                self.sound054 = pygame.mixer.Sound(r'resource\Ukulele\#V.wav')
                self.sound055 = pygame.mixer.Sound(r'resource\Ukulele\B.wav')
                self.sound056 = pygame.mixer.Sound(r'resource\Ukulele\#B.wav')
                self.sound057 = pygame.mixer.Sound(r'resource\Ukulele\N.wav')
                self.sound058 = pygame.mixer.Sound(r'resource\Ukulele\#N.wav')
                self.sound059 = pygame.mixer.Sound(r'resource\Ukulele\M.wav')
                self.sound060 = pygame.mixer.Sound(r'resource\Ukulele\A.wav')
                self.sound061 = pygame.mixer.Sound(r'resource\Ukulele\#A.wav')
                self.sound062 = pygame.mixer.Sound(r'resource\Ukulele\S.wav')
                self.sound063 = pygame.mixer.Sound(r'resource\Ukulele\#S.wav')
                self.sound064 = pygame.mixer.Sound(r'resource\Ukulele\D.wav')
                self.sound065 = pygame.mixer.Sound(r'resource\Ukulele\F.wav')
                self.sound066 = pygame.mixer.Sound(r'resource\Ukulele\#F.wav')
                self.sound067 = pygame.mixer.Sound(r'resource\Ukulele\G.wav')
                self.sound068 = pygame.mixer.Sound(r'resource\Ukulele\#G.wav')
                self.sound069 = pygame.mixer.Sound(r'resource\Ukulele\H.wav')
                self.sound070 = pygame.mixer.Sound(r'resource\Ukulele\#H.wav')
                self.sound071 = pygame.mixer.Sound(r'resource\Ukulele\J.wav')
                self.sound072 = pygame.mixer.Sound(r'resource\Ukulele\Q.wav')
                self.sound074 = pygame.mixer.Sound(r'resource\Ukulele\W.wav')
                self.sound076 = pygame.mixer.Sound(r'resource\Ukulele\E.wav')
                self.sound077 = pygame.mixer.Sound(r'resource\Ukulele\R.wav')
                self.sound079 = pygame.mixer.Sound(r'resource\Ukulele\T.wav')
                self.sound081 = pygame.mixer.Sound(r'resource\Ukulele\Y.wav')
                self.sound083 = pygame.mixer.Sound(r'resource\Ukulele\U.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.mn41.move(388, 387)
            self.mn42.move(513, 387)
            self.mn44.move(888, 387)
            self.mn45.move(1013, 387)
            self.mn47.move(513, 489)
            self.mn50.move(1013, 489)
            self.mn52.move(513, 591)
            self.mn55.move(1013, 591)
            self.mn1.setHidden(True)
            self.mn2.setHidden(True)
            self.mn3.setHidden(True)
            self.mn4.setHidden(True)
            self.mn5.setHidden(True)
            self.mn6.setHidden(True)
            self.mn7.setHidden(True)
            self.mn8.setHidden(False)
            self.mn9.setHidden(False)
            self.mn10.setHidden(False)
            self.mn11.setHidden(False)
            self.mn12.setHidden(False)
            self.mn13.setHidden(False)
            self.mn14.setHidden(False)
            self.mn15.setHidden(False)
            self.mn16.setHidden(False)
            self.mn17.setHidden(False)
            self.mn18.setHidden(False)
            self.mn19.setHidden(False)
            self.mn20.setHidden(False)
            self.mn21.setHidden(False)
            self.mn22.setHidden(False)
            self.mn23.setHidden(False)
            self.mn24.setHidden(False)
            self.mn25.setHidden(False)
            self.mn26.setHidden(False)
            self.mn27.setHidden(False)
            self.mn28.setHidden(False)
            self.mn29.setHidden(False)
            self.mn30.setHidden(False)
            self.mn31.setHidden(False)
            self.mn32.setHidden(False)
            self.mn33.setHidden(False)
            self.mn34.setHidden(False)
            self.mn35.setHidden(False)
            self.mn36.setHidden(True)
            self.mn37.setHidden(True)
            self.mn38.setHidden(True)
            self.mn39.setHidden(True)
            self.mn40.setHidden(True)
            self.mn41.setHidden(True)
            self.mn42.setHidden(True)
            self.mn43.setHidden(True)
            self.mn44.setHidden(True)
            self.mn45.setHidden(True)
            self.mn46.setHidden(False)
            self.mn47.setHidden(False)
            self.mn48.setHidden(False)
            self.mn49.setHidden(False)
            self.mn50.setHidden(False)
            self.mn51.setHidden(False)
            self.mn52.setHidden(False)
            self.mn53.setHidden(False)
            self.mn54.setHidden(False)
            self.mn55.setHidden(False)
            self.mn56.setHidden(False)
            self.mn57.setHidden(False)
            self.mn58.setHidden(False)
            self.mn59.setHidden(False)
            self.mn60.setHidden(False)
            self.mn61.setHidden(True)
            self.mn62.setHidden(True)
            self.mn63.setHidden(True)
            self.mn64.setHidden(True)
            self.mn65.setHidden(True)
            self.mn66.setHidden(True)
            self.mn67.setHidden(True)
            self.mn68.setHidden(True)
            self.mn69.setHidden(True)
            self.mn70.setHidden(True)
            self.mn71.setHidden(True)
            self.mn72.setHidden(True)
            self.mn73.setHidden(True)
            self.mn74.setHidden(True)
            self.mn8.setIcon(QIcon(r'resource\Ukulele\kQ.png'))
            self.mn8.setIconSize(QSize(80, 80))
            self.mn9.setIcon(QIcon(r'resource\Ukulele\kW.png'))
            self.mn9.setIconSize(QSize(80, 80))
            self.mn10.setIcon(QIcon(r'resource\Ukulele\kE.png'))
            self.mn10.setIconSize(QSize(80, 80))
            self.mn11.setIcon(QIcon(r'resource\Ukulele\kR.png'))
            self.mn11.setIconSize(QSize(80, 80))
            self.mn12.setIcon(QIcon(r'resource\Ukulele\kT.png'))
            self.mn12.setIconSize(QSize(80, 80))
            self.mn13.setIcon(QIcon(r'resource\Ukulele\kY.png'))
            self.mn13.setIconSize(QSize(80, 80))
            self.mn14.setIcon(QIcon(r'resource\Ukulele\kU.png'))
            self.mn14.setIconSize(QSize(80, 80))
            self.mn15.setIcon(QIcon(r'resource\Ukulele\kA.png'))
            self.mn15.setIconSize(QSize(80, 80))
            self.mn16.setIcon(QIcon(r'resource\Ukulele\kS.png'))
            self.mn16.setIconSize(QSize(80, 80))
            self.mn17.setIcon(QIcon(r'resource\Ukulele\kD.png'))
            self.mn17.setIconSize(QSize(80, 80))
            self.mn18.setIcon(QIcon(r'resource\Ukulele\kF.png'))
            self.mn18.setIconSize(QSize(80, 80))
            self.mn19.setIcon(QIcon(r'resource\Ukulele\kG.png'))
            self.mn19.setIconSize(QSize(80, 80))
            self.mn20.setIcon(QIcon(r'resource\Ukulele\kH.png'))
            self.mn20.setIconSize(QSize(80, 80))
            self.mn21.setIcon(QIcon(r'resource\Ukulele\kJ.png'))
            self.mn21.setIconSize(QSize(80, 80))
            self.mn22.setIcon(QIcon(r'resource\Ukulele\kA.png'))
            self.mn22.setIconSize(QSize(80, 80))
            self.mn23.setIcon(QIcon(r'resource\Ukulele\kS.png'))
            self.mn23.setIconSize(QSize(80, 80))
            self.mn24.setIcon(QIcon(r'resource\Ukulele\kD.png'))
            self.mn24.setIconSize(QSize(80, 80))
            self.mn25.setIcon(QIcon(r'resource\Ukulele\kF.png'))
            self.mn25.setIconSize(QSize(80, 80))
            self.mn26.setIcon(QIcon(r'resource\Ukulele\kG.png'))
            self.mn26.setIconSize(QSize(80, 80))
            self.mn27.setIcon(QIcon(r'resource\Ukulele\kH.png'))
            self.mn27.setIconSize(QSize(80, 80))
            self.mn28.setIcon(QIcon(r'resource\Ukulele\kJ.png'))
            self.mn28.setIconSize(QSize(80, 80))

        if index == 7:
            self.mn_listener = 8
            self.sound0s.play()
            try:
                self.sound048 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\Z.wav')
                self.sound049 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#Z.wav')
                self.sound050 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\X.wav')
                self.sound051 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#X.wav')
                self.sound052 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\C.wav')
                self.sound053 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\V.wav')
                self.sound054 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#V.wav')
                self.sound055 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\B.wav')
                self.sound056 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#B.wav')
                self.sound057 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\N.wav')
                self.sound058 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#N.wav')
                self.sound059 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\M.wav')
                self.sound060 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\A.wav')
                self.sound061 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#A.wav')
                self.sound062 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\S.wav')
                self.sound063 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#S.wav')
                self.sound064 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\D.wav')
                self.sound065 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\F.wav')
                self.sound066 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#F.wav')
                self.sound067 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\G.wav')
                self.sound068 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#G.wav')
                self.sound069 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\H.wav')
                self.sound070 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#H.wav')
                self.sound071 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\J.wav')
                self.sound072 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\Q.wav')
                self.sound074 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\W.wav')
                self.sound076 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\E.wav')
                self.sound077 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\R.wav')
                self.sound079 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\T.wav')
                self.sound081 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\Y.wav')
                self.sound083 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\U.wav')
                self.sound084 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\1.wav')
                self.sound085 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#1.wav')
                self.sound086 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\2.wav')
                self.sound087 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#2.wav')
                self.sound088 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\3.wav')
                self.sound089 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\4.wav')
                self.sound090 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#4.wav')
                self.sound091 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\5.wav')
                self.sound092 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#5.wav')
                self.sound093 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\6.wav')
                self.sound094 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\#6.wav')
                self.sound095 = pygame.mixer.Sound(r'resource\Lingering_Euphonia\7.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.mn41.move(388, 387)
            self.mn42.move(513, 387)
            self.mn44.move(888, 387)
            self.mn45.move(1013, 387)
            self.mn47.move(513, 489)
            self.mn50.move(1013, 489)
            self.mn52.move(513, 591)
            self.mn55.move(1013, 591)
            self.mn1.setHidden(False)
            self.mn2.setHidden(False)
            self.mn3.setHidden(False)
            self.mn4.setHidden(False)
            self.mn5.setHidden(False)
            self.mn6.setHidden(False)
            self.mn7.setHidden(False)
            self.mn8.setHidden(False)
            self.mn9.setHidden(False)
            self.mn10.setHidden(False)
            self.mn11.setHidden(False)
            self.mn12.setHidden(False)
            self.mn13.setHidden(False)
            self.mn14.setHidden(False)
            self.mn15.setHidden(False)
            self.mn16.setHidden(False)
            self.mn17.setHidden(False)
            self.mn18.setHidden(False)
            self.mn19.setHidden(False)
            self.mn20.setHidden(False)
            self.mn21.setHidden(False)
            self.mn22.setHidden(False)
            self.mn23.setHidden(False)
            self.mn24.setHidden(False)
            self.mn25.setHidden(False)
            self.mn26.setHidden(False)
            self.mn27.setHidden(False)
            self.mn28.setHidden(False)
            self.mn29.setHidden(True)
            self.mn30.setHidden(True)
            self.mn31.setHidden(True)
            self.mn32.setHidden(True)
            self.mn33.setHidden(True)
            self.mn34.setHidden(True)
            self.mn35.setHidden(True)
            self.mn36.setHidden(False)
            self.mn37.setHidden(False)
            self.mn38.setHidden(False)
            self.mn39.setHidden(False)
            self.mn40.setHidden(False)
            self.mn41.setHidden(True)
            self.mn42.setHidden(True)
            self.mn43.setHidden(True)
            self.mn44.setHidden(True)
            self.mn45.setHidden(True)
            self.mn46.setHidden(False)
            self.mn47.setHidden(False)
            self.mn48.setHidden(False)
            self.mn49.setHidden(False)
            self.mn50.setHidden(False)
            self.mn51.setHidden(False)
            self.mn52.setHidden(False)
            self.mn53.setHidden(False)
            self.mn54.setHidden(False)
            self.mn55.setHidden(False)
            self.mn56.setHidden(True)
            self.mn57.setHidden(True)
            self.mn58.setHidden(True)
            self.mn59.setHidden(True)
            self.mn60.setHidden(True)
            self.mn61.setHidden(True)
            self.mn62.setHidden(True)
            self.mn63.setHidden(True)
            self.mn64.setHidden(True)
            self.mn65.setHidden(True)
            self.mn66.setHidden(True)
            self.mn67.setHidden(True)
            self.mn68.setHidden(True)
            self.mn69.setHidden(True)
            self.mn70.setHidden(True)
            self.mn71.setHidden(True)
            self.mn72.setHidden(True)
            self.mn73.setHidden(True)
            self.mn74.setHidden(True)
            self.mn8.setIcon(QIcon(r'resource\Lingering_Euphonia\sQ.png'))
            self.mn8.setIconSize(QSize(80, 80))
            self.mn9.setIcon(QIcon(r'resource\Lingering_Euphonia\sW.png'))
            self.mn9.setIconSize(QSize(80, 80))
            self.mn10.setIcon(QIcon(r'resource\Lingering_Euphonia\sE.png'))
            self.mn10.setIconSize(QSize(80, 80))
            self.mn11.setIcon(QIcon(r'resource\Lingering_Euphonia\sR.png'))
            self.mn11.setIconSize(QSize(80, 80))
            self.mn12.setIcon(QIcon(r'resource\Lingering_Euphonia\sT.png'))
            self.mn12.setIconSize(QSize(80, 80))
            self.mn13.setIcon(QIcon(r'resource\Lingering_Euphonia\sY.png'))
            self.mn13.setIconSize(QSize(80, 80))
            self.mn14.setIcon(QIcon(r'resource\Lingering_Euphonia\sU.png'))
            self.mn14.setIconSize(QSize(80, 80))
            self.mn15.setIcon(QIcon(r'resource\Lingering_Euphonia\sA.png'))
            self.mn15.setIconSize(QSize(80, 80))
            self.mn16.setIcon(QIcon(r'resource\Lingering_Euphonia\sS.png'))
            self.mn16.setIconSize(QSize(80, 80))
            self.mn17.setIcon(QIcon(r'resource\Lingering_Euphonia\sD.png'))
            self.mn17.setIconSize(QSize(80, 80))
            self.mn18.setIcon(QIcon(r'resource\Lingering_Euphonia\sF.png'))
            self.mn18.setIconSize(QSize(80, 80))
            self.mn19.setIcon(QIcon(r'resource\Lingering_Euphonia\sG.png'))
            self.mn19.setIconSize(QSize(80, 80))
            self.mn20.setIcon(QIcon(r'resource\Lingering_Euphonia\sH.png'))
            self.mn20.setIconSize(QSize(80, 80))
            self.mn21.setIcon(QIcon(r'resource\Lingering_Euphonia\sJ.png'))
            self.mn21.setIconSize(QSize(80, 80))
            self.mn22.setIcon(QIcon(r'resource\Lingering_Euphonia\sA.png'))
            self.mn22.setIconSize(QSize(80, 80))
            self.mn23.setIcon(QIcon(r'resource\Lingering_Euphonia\sS.png'))
            self.mn23.setIconSize(QSize(80, 80))
            self.mn24.setIcon(QIcon(r'resource\Lingering_Euphonia\sD.png'))
            self.mn24.setIconSize(QSize(80, 80))
            self.mn25.setIcon(QIcon(r'resource\Lingering_Euphonia\sF.png'))
            self.mn25.setIconSize(QSize(80, 80))
            self.mn26.setIcon(QIcon(r'resource\Lingering_Euphonia\sG.png'))
            self.mn26.setIconSize(QSize(80, 80))
            self.mn27.setIcon(QIcon(r'resource\Lingering_Euphonia\sH.png'))
            self.mn27.setIconSize(QSize(80, 80))
            self.mn28.setIcon(QIcon(r'resource\Lingering_Euphonia\sJ.png'))
            self.mn28.setIconSize(QSize(80, 80))
            
        if index == 2:
            self.mn_listener = 3
            self.sound0h.play()
            try:
                self.sound060 = pygame.mixer.Sound(r'resource\Festive_Drum\A.wav')
                self.sound062 = pygame.mixer.Sound(r'resource\Festive_Drum\S.wav')
                self.sound069 = pygame.mixer.Sound(r'resource\Festive_Drum\S.wav')
                self.sound071 = pygame.mixer.Sound(r'resource\Festive_Drum\A.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.mn41.move(388, 387)
            self.mn42.move(513, 387)
            self.mn44.move(888, 387)
            self.mn45.move(1013, 387)
            self.mn47.move(513, 489)
            self.mn50.move(1013, 489)
            self.mn52.move(513, 591)
            self.mn55.move(1013, 591)
            self.mn1.setHidden(True)
            self.mn2.setHidden(True)
            self.mn3.setHidden(True)
            self.mn4.setHidden(True)
            self.mn5.setHidden(True)
            self.mn6.setHidden(True)
            self.mn7.setHidden(True)
            self.mn8.setHidden(True)
            self.mn9.setHidden(True)
            self.mn10.setHidden(True)
            self.mn11.setHidden(True)
            self.mn12.setHidden(True)
            self.mn13.setHidden(True)
            self.mn14.setHidden(True)
            self.mn15.setHidden(False)
            self.mn16.setHidden(False)
            self.mn17.setHidden(True)
            self.mn18.setHidden(True)
            self.mn19.setHidden(True)
            self.mn20.setHidden(False)
            self.mn21.setHidden(False)
            self.mn22.setHidden(True)
            self.mn23.setHidden(True)
            self.mn24.setHidden(True)
            self.mn25.setHidden(True)
            self.mn26.setHidden(True)
            self.mn27.setHidden(True)
            self.mn28.setHidden(True)
            self.mn29.setHidden(True)
            self.mn30.setHidden(True)
            self.mn31.setHidden(True)
            self.mn32.setHidden(True)
            self.mn33.setHidden(True)
            self.mn34.setHidden(True)
            self.mn35.setHidden(True)
            self.mn36.setHidden(True)
            self.mn37.setHidden(True)
            self.mn38.setHidden(True)
            self.mn39.setHidden(True)
            self.mn40.setHidden(True)
            self.mn41.setHidden(True)
            self.mn42.setHidden(True)
            self.mn43.setHidden(True)
            self.mn44.setHidden(True)
            self.mn45.setHidden(True)
            self.mn46.setHidden(True)
            self.mn47.setHidden(True)
            self.mn48.setHidden(True)
            self.mn49.setHidden(True)
            self.mn50.setHidden(True)
            self.mn51.setHidden(True)
            self.mn52.setHidden(True)
            self.mn53.setHidden(True)
            self.mn54.setHidden(True)
            self.mn55.setHidden(True)
            self.mn56.setHidden(True)
            self.mn57.setHidden(True)
            self.mn58.setHidden(True)
            self.mn59.setHidden(True)
            self.mn60.setHidden(True)
            self.mn61.setHidden(True)
            self.mn62.setHidden(True)
            self.mn63.setHidden(True)
            self.mn64.setHidden(True)
            self.mn65.setHidden(True)
            self.mn66.setHidden(True)
            self.mn67.setHidden(True)
            self.mn68.setHidden(True)
            self.mn69.setHidden(True)
            self.mn70.setHidden(True)
            self.mn71.setHidden(True)
            self.mn72.setHidden(True)
            self.mn73.setHidden(True)
            self.mn74.setHidden(True)
            self.mn15.setIcon(QIcon(r'resource\Festive_Drum\hA.png'))
            self.mn15.setIconSize(QSize(80, 80))
            self.mn16.setIcon(QIcon(r'resource\Festive_Drum\hS.png'))
            self.mn16.setIconSize(QSize(80, 80))
            self.mn20.setIcon(QIcon(r'resource\Festive_Drum\hS.png'))
            self.mn20.setIconSize(QSize(80, 80))
            self.mn21.setIcon(QIcon(r'resource\Festive_Drum\hA.png'))
            self.mn21.setIconSize(QSize(80, 80))

        if index == 6:
            self.mn_listener = 7
            self.sound0g.play()
            try:
                self.sound060 = pygame.mixer.Sound(r'resource\Djem_Djem_Drum\A.wav')
                self.sound062 = pygame.mixer.Sound(r'resource\Djem_Djem_Drum\S.wav')
                self.sound069 = pygame.mixer.Sound(r'resource\Djem_Djem_Drum\K.wav')
                self.sound071 = pygame.mixer.Sound(r'resource\Djem_Djem_Drum\L.wav')
                self.sound072 = pygame.mixer.Sound(r'resource\Djem_Djem_Drum\Q.wav')
                self.sound074 = pygame.mixer.Sound(r'resource\Djem_Djem_Drum\W.wav')
                self.sound081 = pygame.mixer.Sound(r'resource\Djem_Djem_Drum\I.wav')
                self.sound083 = pygame.mixer.Sound(r'resource\Djem_Djem_Drum\O.wav')
            except Exception as e:
                QMessageBox.warning(self, '警告', '音频加载失败！')
            self.mn41.move(388, 387)
            self.mn42.move(513, 387)
            self.mn44.move(888, 387)
            self.mn45.move(1013, 387)
            self.mn47.move(513, 489)
            self.mn50.move(1013, 489)
            self.mn52.move(513, 591)
            self.mn55.move(1013, 591)
            self.mn1.setHidden(True)
            self.mn2.setHidden(True)
            self.mn3.setHidden(True)
            self.mn4.setHidden(True)
            self.mn5.setHidden(True)
            self.mn6.setHidden(True)
            self.mn7.setHidden(True)
            self.mn8.setHidden(False)
            self.mn9.setHidden(False)
            self.mn10.setHidden(True)
            self.mn11.setHidden(True)
            self.mn12.setHidden(True)
            self.mn13.setHidden(False)
            self.mn14.setHidden(False)
            self.mn15.setHidden(False)
            self.mn16.setHidden(False)
            self.mn17.setHidden(True)
            self.mn18.setHidden(True)
            self.mn19.setHidden(True)
            self.mn20.setHidden(False)
            self.mn21.setHidden(False)
            self.mn22.setHidden(True)
            self.mn23.setHidden(True)
            self.mn24.setHidden(True)
            self.mn25.setHidden(True)
            self.mn26.setHidden(True)
            self.mn27.setHidden(True)
            self.mn28.setHidden(True)
            self.mn29.setHidden(True)
            self.mn30.setHidden(True)
            self.mn31.setHidden(True)
            self.mn32.setHidden(True)
            self.mn33.setHidden(True)
            self.mn34.setHidden(True)
            self.mn35.setHidden(True)
            self.mn36.setHidden(True)
            self.mn37.setHidden(True)
            self.mn38.setHidden(True)
            self.mn39.setHidden(True)
            self.mn40.setHidden(True)
            self.mn41.setHidden(True)
            self.mn42.setHidden(True)
            self.mn43.setHidden(True)
            self.mn44.setHidden(True)
            self.mn45.setHidden(True)
            self.mn46.setHidden(True)
            self.mn47.setHidden(True)
            self.mn48.setHidden(True)
            self.mn49.setHidden(True)
            self.mn50.setHidden(True)
            self.mn51.setHidden(True)
            self.mn52.setHidden(True)
            self.mn53.setHidden(True)
            self.mn54.setHidden(True)
            self.mn55.setHidden(True)
            self.mn56.setHidden(True)
            self.mn57.setHidden(True)
            self.mn58.setHidden(True)
            self.mn59.setHidden(True)
            self.mn60.setHidden(True)
            self.mn61.setHidden(True)
            self.mn62.setHidden(True)
            self.mn63.setHidden(True)
            self.mn64.setHidden(True)
            self.mn65.setHidden(True)
            self.mn66.setHidden(True)
            self.mn67.setHidden(True)
            self.mn68.setHidden(True)
            self.mn69.setHidden(True)
            self.mn70.setHidden(True)
            self.mn71.setHidden(True)
            self.mn72.setHidden(True)
            self.mn73.setHidden(True)
            self.mn74.setHidden(True)
            self.mn15.setIcon(QIcon(r'resource\Djem_Djem_Drum\gQ.png'))
            self.mn15.setIconSize(QSize(80, 80))
            self.mn16.setIcon(QIcon(r'resource\Djem_Djem_Drum\gW.png'))
            self.mn16.setIconSize(QSize(80, 80))
            self.mn20.setIcon(QIcon(r'resource\Djem_Djem_Drum\gI.png'))
            self.mn20.setIconSize(QSize(80, 80))
            self.mn21.setIcon(QIcon(r'resource\Djem_Djem_Drum\gO.png'))
            self.mn21.setIconSize(QSize(80, 80))
            self.mn8.setIcon(QIcon(r'resource\Djem_Djem_Drum\gQ.png'))
            self.mn8.setIconSize(QSize(80, 80))
            self.mn9.setIcon(QIcon(r'resource\Djem_Djem_Drum\gW.png'))
            self.mn9.setIconSize(QSize(80, 80))
            self.mn13.setIcon(QIcon(r'resource\Djem_Djem_Drum\gI.png'))
            self.mn13.setIconSize(QSize(80, 80))
            self.mn14.setIcon(QIcon(r'resource\Djem_Djem_Drum\gO.png'))
            self.mn14.setIconSize(QSize(80, 80))

        if index == 4:
            self.mn_listener = 5
            self.sound0w.play()
            self.mn1.setHidden(True)
            self.mn2.setHidden(True)
            self.mn3.setHidden(True)
            self.mn4.setHidden(True)
            self.mn5.setHidden(True)
            self.mn6.setHidden(True)
            self.mn7.setHidden(True)
            self.mn8.setHidden(True)
            self.mn9.setHidden(True)
            self.mn10.setHidden(True)
            self.mn11.setHidden(True)
            self.mn12.setHidden(True)
            self.mn13.setHidden(True)
            self.mn14.setHidden(True)
            self.mn15.setHidden(True)
            self.mn16.setHidden(True)
            self.mn17.setHidden(True)
            self.mn18.setHidden(True)
            self.mn19.setHidden(True)
            self.mn20.setHidden(True)
            self.mn21.setHidden(True)
            self.mn22.setHidden(True)
            self.mn23.setHidden(True)
            self.mn24.setHidden(True)
            self.mn25.setHidden(True)
            self.mn26.setHidden(True)
            self.mn27.setHidden(True)
            self.mn28.setHidden(True)
            self.mn29.setHidden(True)
            self.mn30.setHidden(True)
            self.mn31.setHidden(True)
            self.mn32.setHidden(True)
            self.mn33.setHidden(True)
            self.mn34.setHidden(True)
            self.mn35.setHidden(True)
            self.mn36.setHidden(True)
            self.mn37.setHidden(True)
            self.mn38.setHidden(True)
            self.mn39.setHidden(True)
            self.mn40.setHidden(True)
            self.mn41.setHidden(True)
            self.mn42.setHidden(True)
            self.mn43.setHidden(True)
            self.mn44.setHidden(True)
            self.mn45.setHidden(True)
            self.mn46.setHidden(True)
            self.mn47.setHidden(True)
            self.mn48.setHidden(True)
            self.mn49.setHidden(True)
            self.mn50.setHidden(True)
            self.mn51.setHidden(True)
            self.mn52.setHidden(True)
            self.mn53.setHidden(True)
            self.mn54.setHidden(True)
            self.mn55.setHidden(True)
            self.mn56.setHidden(True)
            self.mn57.setHidden(True)
            self.mn58.setHidden(True)
            self.mn59.setHidden(True)
            self.mn60.setHidden(True)
            self.mn61.setHidden(False)
            self.mn62.setHidden(False)
            self.mn63.setHidden(False)
            self.mn64.setHidden(False)
            self.mn65.setHidden(False)
            self.mn66.setHidden(False)
            self.mn67.setHidden(False)
            self.mn68.setHidden(False)
            self.mn69.setHidden(False)
            self.mn70.setHidden(False)
            self.mn71.setHidden(False)
            self.mn72.setHidden(False)
            self.mn73.setHidden(False)
            self.mn74.setHidden(False)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
    
        key = event.key()
    
        if self.mn_listener in {1, 2, 4, 9, 10, 6, 8, 3, 7}:
            if self.mn_listener in {1, 2, 4, 9, 10}:
                if key == 65:    # A
                    self.sound060.play()
                elif key == 83:   # S
                    self.sound062.play()
                elif key == 68:   # D
                    self.sound064.play()
                elif key == 70:   # F
                    self.sound065.play()
                elif key == 71:   # G
                    self.sound067.play()
                elif key == 72:   # H
                    self.sound069.play()
                elif key == 74:   # J
                    self.sound071.play()
                elif key == 90:   # Z
                    self.sound048.play()
                elif key == 88:   # X
                    self.sound050.play()
                elif key == 67:   # C
                    self.sound052.play()
                elif key == 86:   # V
                    self.sound053.play()
                elif key == 66:   # B
                    self.sound055.play()
                elif key == 78:   # N
                    self.sound057.play()
                elif key == 77:   # M
                    self.sound059.play()
                elif key == 81:   # Q
                    self.sound072.play()
                elif key == 87:   # W
                    self.sound074.play()
                elif key == 69:   # E
                    self.sound076.play()
                elif key == 82:   # R
                    self.sound077.play()
                elif key == 84:   # T
                    self.sound079.play()
                elif key == 89:   # Y
                    self.sound081.play()
                elif key == 85:   # U
                    self.sound083.play()
                elif key == 49:   # 1
                    self.sound084.play()
                elif key == 50:   # 2
                    self.sound086.play()
                elif key == 51:   # 3
                    self.sound088.play()
                elif key == 52:   # 4
                    self.sound089.play()
                elif key == 53:   # 5
                    self.sound091.play()
                elif key == 54:   # 6
                    self.sound093.play()
                elif key == 55:   # 7
                    self.sound095.play()
                elif key == 44:   # Comma (,)
                    self.sound036.play()
                elif key == 46:   # Period (.)
                    self.sound038.play()
                elif key == 47:   # Slash (/)
                    self.sound040.play()
                elif key == 59:   # Semicolon (;)
                    self.sound041.play()
                elif key == 39:   # Apostrophe (')
                    self.sound043.play()
                elif key == 91:   # Bracketleft ([)
                    self.sound045.play()
                elif key == 93:   # Bracketright (])
                    self.sound047.play()
        
            if self.mn_listener == 6:
                if key == 65:    # A
                    self.sound060.play()
                elif key == 83:   # S
                    self.sound062.play()
                elif key == 68:   # D
                    self.sound064.play()
                elif key == 70:   # F
                    self.sound065.play()
                elif key == 71:   # G
                    self.sound067.play()
                elif key == 72:   # H
                    self.sound069.play()
                elif key == 74:   # J
                    self.sound071.play()
                elif key == 90:   # Z
                    self.sound048.play()
                elif key == 88:   # X
                    self.sound050.play()
                elif key == 67:   # C
                    self.sound052.play()
                elif key == 86:   # V
                    self.sound053.play()
                elif key == 66:   # B
                    self.sound055.play()
                elif key == 78:   # N
                    self.sound057.play()
                elif key == 77:   # M
                    self.sound059.play()
                elif key == 81:   # Q
                    self.sound072.play()
                elif key == 87:   # W
                    self.sound074.play()
                elif key == 69:   # E
                    self.sound076.play()
                elif key == 82:   # R
                    self.sound077.play()
                elif key == 84:   # T
                    self.sound079.play()
                elif key == 89:   # Y
                    self.sound081.play()
                elif key == 85:   # U
                    self.sound083.play()
                elif key == 44:   # Comma (,)
                    self.sound036.play()
                elif key == 46:   # Period (.)
                    self.sound038.play()
                elif key == 47:   # Slash (/)
                    self.sound040.play()
                elif key == 59:   # Semicolon (;)
                    self.sound041.play()
                elif key == 39:   # Apostrophe (')
                    self.sound043.play()
                elif key == 91:   # Bracketleft ([)
                    self.sound045.play()
                elif key == 93:   # Bracketright (])
                    self.sound047.play()
        
            if self.mn_listener == 8:
                if key == 65:    # A
                    self.sound060.play()
                elif key == 83:   # S
                    self.sound062.play()
                elif key == 68:   # D
                    self.sound064.play()
                elif key == 70:   # F
                    self.sound065.play()
                elif key == 71:   # G
                    self.sound067.play()
                elif key == 72:   # H
                    self.sound069.play()
                elif key == 74:   # J
                    self.sound071.play()
                elif key == 90:   # Z
                    self.sound048.play()
                elif key == 88:   # X
                    self.sound050.play()
                elif key == 67:   # C
                    self.sound052.play()
                elif key == 86:   # V
                    self.sound053.play()
                elif key == 66:   # B
                    self.sound055.play()
                elif key == 78:   # N
                    self.sound057.play()
                elif key == 77:   # M
                    self.sound059.play()
                elif key == 81:   # Q
                    self.sound072.play()
                elif key == 87:   # W
                    self.sound074.play()
                elif key == 69:   # E
                    self.sound076.play()
                elif key == 82:   # R
                    self.sound077.play()
                elif key == 84:   # T
                    self.sound079.play()
                elif key == 89:   # Y
                    self.sound081.play()
                elif key == 85:   # U
                    self.sound083.play()
                elif key == 49:   # 1
                    self.sound084.play()
                elif key == 50:   # 2
                    self.sound086.play()
                elif key == 51:   # 3
                    self.sound088.play()
                elif key == 52:   # 4
                    self.sound089.play()
                elif key == 53:   # 5
                    self.sound091.play()
                elif key == 54:   # 6
                    self.sound093.play()
                elif key == 55:   # 7
                    self.sound095.play()
        
            if self.mn_listener == 3:
                if key == 65:    # A
                    self.sound060.play()
                elif key == 83:   # S
                    self.sound062.play()
                elif key == 75:   # K
                    self.sound069.play()
                elif key == 76:   # L
                    self.sound071.play()
        
            if self.mn_listener == 7:
                if key == 65:    # A
                    self.sound060.play()
                elif key == 83:   # S
                    self.sound062.play()
                elif key == 75:   # K
                    self.sound069.play()
                elif key == 76:   # L
                    self.sound071.play()
                elif key == 81:   # Q
                    self.sound072.play()
                elif key == 87:   # W
                    self.sound074.play()
                elif key == 73:   # I
                    self.sound081.play()
                elif key == 79:   # O
                    self.sound083.play()
    
        # 处理 mn_listener 为 5 的情况
        elif self.mn_listener == 5:
            if key == 65:
                self.playing_A = self.sound008.play()
            elif key == 83:
                self.playing_S = self.sound009.play()
            elif key == 68:
                self.playing_D = self.sound010.play()
            elif key == 70:
                self.playing_F = self.sound011.play()
            elif key == 71:
                self.playing_G = self.sound012.play()
            elif key == 72:
                self.playing_H = self.sound013.play()
            elif key == 74:
                self.playing_J = self.sound014.play()
            elif key == 90:
                self.playing_Z = self.sound001.play()
            elif key == 88:
                self.playing_X = self.sound002.play()
            elif key == 67:
                self.playing_C = self.sound003.play()
            elif key == 86:
                self.playing_V = self.sound004.play()
            elif key == 66:
                self.playing_B = self.sound005.play()
            elif key == 78:
                self.playing_N = self.sound006.play()
            elif key == 77:
                self.playing_M = self.sound007.play()
    
    def keyReleaseEvent(self, event):
        if self.mn_listener != 5:
            return

        if event.isAutoRepeat():
            return
        key = event.key()
        
        if key == 65:
            self.playing_A.fadeout(500)
        elif key == 83:
            self.playing_S.fadeout(500)
        elif key == 68:
            self.playing_D.fadeout(500)
        elif key == 70:
            self.playing_F.fadeout(500)
        elif key == 71:
            self.playing_G.fadeout(500)
        elif key == 72:
            self.playing_H.fadeout(500)
        elif key == 74:
            self.playing_J.fadeout(500)
        elif key == 90:
            self.playing_Z.fadeout(500)
        elif key == 88:
            self.playing_X.fadeout(500)
        elif key == 67:
            self.playing_C.fadeout(500)
        elif key == 86:
            self.playing_V.fadeout(500)
        elif key == 66:
            self.playing_B.fadeout(500)
        elif key == 78:
            self.playing_N.fadeout(500)
        elif key == 77:
            self.playing_M.fadeout(500)

    def start_mn_mapping(self):
        if self.current_device is not None:
            self.midi_in.close_port()
        
        device_index = self.mn76.currentData()
        if device_index is None:
            self.mn84.setText("错误，请选择有效的MIDI设备！")
            QTimer.singleShot(3000, self.clear_label4)
            return
        
        try:
            self.midi_in.open_port(device_index)
            self.midi_in.set_callback(self.mn_midi_callback)
            self.current_device = device_index
            self.mapping_active = True
            
            self.mn78.setEnabled(False)
            self.mn79.setEnabled(True)
            device_name = self.mn76.currentText()
            
        except Exception as e:
            self.stop_mn_mapping()
            self.mn84.setText("连接错误，无法打开MIDI设备！")
            QTimer.singleShot(3000, self.clear_label4)

    def stop_mn_mapping(self):
        """停止MIDI映射"""
        
        if not hasattr(self, 'mapping_active') or not self.mapping_active:
            return
        
        try:
            if hasattr(self, 'midi_in') and self.midi_in:
                self.midi_in.close_port()
            
            if hasattr(self, 'active_notes'):
                self.active_notes.clear()
            
            self.mapping_active = False
            if hasattr(self, 'current_device'):
                self.current_device = None
        except:
            pass
        
        if hasattr(self, 'mn78') and hasattr(self, 'mn79'):
            self.mn78.setEnabled(True)
            self.mn79.setEnabled(False)

    def mn_midi_callback(self, event, data=None):
        """MIDI输入回调函数"""
        message, delta_time = event
        
        if len(message) < 3:
            return
    
        status = message[0] & 0xF0
        note = message[1]
        velocity = message[2]
    
        if status == 0x90 and velocity > 0:
            self.mn_handle_note_on(note)
        elif status == 0x80 or (status == 0x90 and velocity == 0):
            self.mn_handle_note_off(note)

    def mn_handle_note_on(self, note):
        """处理音符按下事件"""
        if self.mn_listener in {1, 2, 4, 9, 10, 6, 8}:
            if self.mn_listener in {1, 2, 9, 10}:
                if note == 36:
                    self.sound036.play()
                if note == 37:
                    self.sound037.play()
                if note == 38:
                    self.sound038.play()
                if note == 39:
                    self.sound039.play()
                if note == 40:
                    self.sound040.play()
                if note == 41:
                    self.sound041.play()
                if note == 42:
                    self.sound042.play()
                if note == 43:
                    self.sound043.play()
                if note == 44:
                    self.sound044.play()
                if note == 45:
                    self.sound045.play()
                if note == 46:
                    self.sound046.play()
                if note == 47:
                    self.sound047.play()
                if note == 48:
                    self.sound048.play()
                if note == 49:
                    self.sound049.play()
                if note == 50:
                    self.sound050.play()
                if note == 51:
                    self.sound051.play()
                if note == 52:
                    self.sound052.play()
                if note == 53:
                    self.sound053.play()
                if note == 54:
                    self.sound054.play()
                if note == 55:
                    self.sound055.play()
                if note == 56:
                    self.sound056.play()
                if note == 57:
                    self.sound057.play()
                if note == 58:
                    self.sound058.play()
                if note == 59:
                    self.sound059.play()
                if note == 60:
                    self.sound060.play()
                if note == 61:
                    self.sound061.play()
                if note == 62:
                    self.sound062.play()
                if note == 63:
                    self.sound063.play()
                if note == 64:
                    self.sound064.play()
                if note == 65:
                    self.sound065.play()
                if note == 66:
                    self.sound066.play()
                if note == 67:
                    self.sound067.play()
                if note == 68:
                    self.sound068.play()
                if note == 69:
                    self.sound069.play()
                if note == 70:
                    self.sound070.play()
                if note == 71:
                    self.sound071.play()
                if note == 72:
                    self.sound072.play()
                if note == 73:
                    self.sound073.play()
                if note == 74:
                    self.sound074.play()
                if note == 75:
                    self.sound075.play()
                if note == 76:
                    self.sound076.play()
                if note == 77:
                    self.sound077.play()
                if note == 78:
                    self.sound078.play()
                if note == 79:
                    self.sound079.play()
                if note == 80:
                    self.sound080.play()
                if note == 81:
                    self.sound081.play()
                if note == 82:
                    self.sound082.play()
                if note == 83:
                    self.sound083.play()
                if note == 84:
                    self.sound084.play()
                if note == 85:
                    self.sound085.play()
                if note == 86:
                    self.sound086.play()
                if note == 87:
                    self.sound087.play()
                if note == 88:
                    self.sound088.play()
                if note == 89:
                    self.sound089.play()
                if note == 90:
                    self.sound090.play()
                if note == 91:
                    self.sound091.play()
                if note == 92:
                    self.sound092.play()
                if note == 93:
                    self.sound093.play()
                if note == 94:
                    self.sound094.play()
                if note == 95:
                    self.sound095.play()
            if self.mn_listener == 4:
                if note == 36:
                    self.sound036.play()
                if note == 37:
                    self.sound037.play()
                if note == 38:
                    self.sound038.play()
                if note == 39:
                    self.sound039.play()
                if note == 40:
                    self.sound040.play()
                if note == 41:
                    self.sound041.play()
                if note == 42:
                    self.sound042.play()
                if note == 43:
                    self.sound043.play()
                if note == 44:
                    self.sound044.play()
                if note == 45:
                    self.sound045.play()
                if note == 46:
                    self.sound046.play()
                if note == 47:
                    self.sound047.play()
                if note == 48:
                    self.sound048.play()
                if note == 49:
                    self.sound049.play()
                if note == 50:
                    self.sound050.play()
                if note == 51:
                    self.sound052.play()
                if note == 52:
                    self.sound051.play()
                if note == 53:
                    self.sound053.play()
                if note == 54:
                    self.sound054.play()
                if note == 55:
                    self.sound055.play()
                if note == 56:
                    self.sound056.play()
                if note == 57:
                    self.sound057.play()
                if note == 58:
                    self.sound059.play()
                if note == 59:
                    self.sound058.play()
                if note == 60:
                    self.sound060.play()
                if note == 61:
                    self.sound061.play()
                if note == 62:
                    self.sound062.play()
                if note == 63:
                    self.sound064.play()
                if note == 64:
                    self.sound063.play()
                if note == 65:
                    self.sound065.play()
                if note == 66:
                    self.sound066.play()
                if note == 67:
                    self.sound067.play()
                if note == 68:
                    self.sound068.play()
                if note == 69:
                    self.sound069.play()
                if note == 70:
                    self.sound071.play()
                if note == 71:
                    self.sound070.play()
                if note == 72:
                    self.sound072.play()
                if note == 73:
                    self.sound074.play()
                if note == 74:
                    self.sound073.play()
                if note == 75:
                    self.sound076.play()
                if note == 76:
                    self.sound075.play()
                if note == 77:
                    self.sound077.play()
                if note == 78:
                    self.sound078.play()
                if note == 79:
                    self.sound079.play()
                if note == 80:
                    self.sound081.play()
                if note == 81:
                    self.sound080.play()
                if note == 82:
                    self.sound083.play()
                if note == 83:
                    self.sound082.play()
                if note == 84:
                    self.sound084.play()
                if note == 85:
                    self.sound085.play()
                if note == 86:
                    self.sound086.play()
                if note == 87:
                    self.sound087.play()
                if note == 88:
                    self.sound088.play()
                if note == 89:
                    self.sound089.play()
                if note == 90:
                    self.sound090.play()
                if note == 91:
                    self.sound091.play()
                if note == 92:
                    self.sound092.play()
                if note == 93:
                    self.sound093.play()
                if note == 94:
                    self.sound094.play()
                if note == 95:
                    self.sound095.play()
            if self.mn_listener == 6:
                if note == 36:
                    self.sound072.play()
                if note == 38:
                    self.sound074.play()
                if note == 40:
                    self.sound076.play()
                if note == 41:
                    self.sound077.play()
                if note == 43:
                    self.sound079.play()
                if note == 45:
                    self.sound081.play()
                if note == 47:
                    self.sound083.play()
                if note == 48:
                    self.sound036.play()
                if note == 49:
                    self.sound037.play()
                if note == 50:
                    self.sound038.play()
                if note == 51:
                    self.sound039.play()
                if note == 52:
                    self.sound040.play()
                if note == 53:
                    self.sound041.play()
                if note == 54:
                    self.sound042.play()
                if note == 55:
                    self.sound043.play()
                if note == 56:
                    self.sound044.play()
                if note == 57:
                    self.sound045.play()
                if note == 58:
                    self.sound046.play()
                if note == 59:
                    self.sound047.play()
                if note == 60:
                    self.sound048.play()
                if note == 61:
                    self.sound049.play()
                if note == 62:
                    self.sound050.play()
                if note == 63:
                    self.sound051.play()
                if note == 64:
                    self.sound052.play()
                if note == 65:
                    self.sound053.play()
                if note == 66:
                    self.sound054.play()
                if note == 67:
                    self.sound055.play()
                if note == 68:
                    self.sound056.play()
                if note == 69:
                    self.sound057.play()
                if note == 70:
                    self.sound058.play()
                if note == 71:
                    self.sound059.play()
                if note == 72:
                    self.sound060.play()
                if note == 73:
                    self.sound061.play()
                if note == 74:
                    self.sound062.play()
                if note == 75:
                    self.sound063.play()
                if note == 76:
                    self.sound064.play()
                if note == 77:
                    self.sound065.play()
                if note == 78:
                    self.sound066.play()
                if note == 79:
                    self.sound067.play()
                if note == 80:
                    self.sound068.play()
                if note == 81:
                    self.sound069.play()
                if note == 82:
                    self.sound070.play()
                if note == 83:
                    self.sound071.play()
            if self.mn_listener == 8:
                if note == 36:
                    self.sound072.play()
                if note == 38:
                    self.sound074.play()
                if note == 40:
                    self.sound076.play()
                if note == 41:
                    self.sound077.play()
                if note == 43:
                    self.sound079.play()
                if note == 45:
                    self.sound081.play()
                if note == 47:
                    self.sound083.play()
                if note == 48:
                    self.sound048.play()
                if note == 49:
                    self.sound049.play()
                if note == 50:
                    self.sound050.play()
                if note == 51:
                    self.sound051.play()
                if note == 52:
                    self.sound052.play()
                if note == 53:
                    self.sound053.play()
                if note == 54:
                    self.sound054.play()
                if note == 55:
                    self.sound055.play()
                if note == 56:
                    self.sound056.play()
                if note == 57:
                    self.sound057.play()
                if note == 58:
                    self.sound058.play()
                if note == 59:
                    self.sound059.play()
                if note == 60:
                    self.sound060.play()
                if note == 61:
                    self.sound061.play()
                if note == 62:
                    self.sound062.play()
                if note == 63:
                    self.sound063.play()
                if note == 64:
                    self.sound064.play()
                if note == 65:
                    self.sound065.play()
                if note == 66:
                    self.sound066.play()
                if note == 67:
                    self.sound067.play()
                if note == 68:
                    self.sound068.play()
                if note == 69:
                    self.sound069.play()
                if note == 70:
                    self.sound070.play()
                if note == 71:
                    self.sound071.play()
                if note == 72:
                    self.sound084.play()
                if note == 73:
                    self.sound085.play()
                if note == 74:
                    self.sound086.play()
                if note == 75:
                    self.sound087.play()
                if note == 76:
                    self.sound088.play()
                if note == 77:
                    self.sound089.play()
                if note == 78:
                    self.sound090.play()
                if note == 79:
                    self.sound091.play()
                if note == 80:
                    self.sound092.play()
                if note == 81:
                    self.sound093.play()
                if note == 82:
                    self.sound094.play()
                if note == 83:
                    self.sound095.play()
        if self.mn_listener == 5:
            if note == 60:
                self.playing_A = self.sound008.play()
            elif note == 62:
                self.playing_S = self.sound009.play()
            elif note == 64:
                self.playing_D = self.sound010.play()
            elif note == 65:
                self.playing_F = self.sound011.play()
            elif note == 67:
                self.playing_G = self.sound012.play()
            elif note == 69:
                self.playing_H = self.sound013.play()
            elif note == 71:
                self.playing_J = self.sound014.play()
            elif note == 48:
                self.playing_Z = self.sound001.play()
            elif note == 50:
                self.playing_X = self.sound002.play()
            elif note == 52:
                self.playing_C = self.sound003.play()
            elif note == 53:
                self.playing_V = self.sound004.play()
            elif note == 55:
                self.playing_B = self.sound005.play()
            elif note == 57:
                self.playing_N = self.sound006.play()
            elif note == 59:
                self.playing_M = self.sound007.play()

    
    def mn_handle_note_off(self, note):
        if self.mn_listener != 5:
            return

        if note == 60:
            self.playing_A.fadeout(500)
        elif note == 62:
            self.playing_S.fadeout(500)
        elif note == 64:
            self.playing_D.fadeout(500)
        elif note == 65:
            self.playing_F.fadeout(500)
        elif note == 67:
            self.playing_G.fadeout(500)
        elif note == 69:
            self.playing_H.fadeout(500)
        elif note == 71:
            self.playing_J.fadeout(500)
        elif note == 48:
            self.playing_Z.fadeout(500)
        elif note == 50:
            self.playing_X.fadeout(500)
        elif note == 52:
            self.playing_C.fadeout(500)
        elif note == 53:
            self.playing_V.fadeout(500)
        elif note == 55:
            self.playing_B.fadeout(500)
        elif note == 57:
            self.playing_N.fadeout(500)
        elif note == 59:
            self.playing_M.fadeout(500)

    def start_playback(self):
        if not self.mn_timer.isActive():
            try:
                self.mn_bpm = int(self.mn80.text())
                if self.mn_bpm < 0:
                    self.mn84.setText("时间输入错误！")
                    QTimer.singleShot(3000, self.clear_label4)
                    return
            except ValueError as e:
                self.mn84.setText("时间输入错误！")
                QTimer.singleShot(3000, self.clear_label4)
                return
            self.timer_interval = round(60 / self.mn_bpm, 2)*1000
            self.current_index = 0
            self.play_current()
            self.mn_timer.start(self.timer_interval)
            self.mn82.setEnabled(False)
            self.mn83.setEnabled(True)
            
    def stop_playback(self):
        self.mn_timer.stop()
        self.mn82.setEnabled(True)
        self.mn83.setEnabled(False)
        
    def play_current(self):
        sound = self.sound0001 if self.sequence[self.current_index] == 0 else self.sound0002
        sound.play()  # 自动分配通道
        
    def play_next(self):
        self.current_index = (self.current_index + 1) % len(self.sequence)
        self.play_current()

    def mn81p(self, index):
        if index == 0:
            self.sequence = [0, 1, 1, 1]
        if index == 1:
            self.sequence = [0, 1, 1]

    def clear_label4(self):
        self.mn84.clear()

    def update_background(self):
        if self.background_read is None:
            self.backgroundlabel.clear()
            self.setObjectName("MainWindow")
            if darkdetect.theme() == 'Light':
                self.setStyleSheet("QWidget#MainWindow { background-color: white; }")
                self.Label1.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.yz5.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.yz6.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.yz7.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.yz10.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.bj36.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.bj43.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.bj48.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.bj51.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.jy1.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.jy6.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.my2.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.my4.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.my8.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.mn84.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.mn85.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.mn86.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.mn87.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.mn88.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.sz1.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.sz3.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.sz4.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.sz7.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.sz9.setStyleSheet(f'color: rgb(0, 0, 0);')
                self.dh1.setStyleSheet('')
                self.dh2.setStyleSheet('')
                self.dh3.setStyleSheet('')
                self.dh4.setStyleSheet('')
                self.dh5.setStyleSheet('')
                self.dh6.setStyleSheet('')
                self.dh7.setStyleSheet('')
                
            if darkdetect.theme() == 'Dark':
                self.setStyleSheet("QWidget#MainWindow { background-color: rgb(41, 42, 45); }")
                self.Label1.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.yz5.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.yz6.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.yz7.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.yz10.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.bj36.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.bj43.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.bj48.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.bj51.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.jy1.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.jy6.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.my2.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.my4.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.my8.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.mn84.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.mn85.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.mn86.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.mn87.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.mn88.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.sz1.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.sz3.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.sz4.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.sz7.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.sz9.setStyleSheet(f'color: rgb(255, 255, 255);')
                self.dh1.setStyleSheet('')
                self.dh2.setStyleSheet('')
                self.dh3.setStyleSheet('')
                self.dh4.setStyleSheet('')
                self.dh5.setStyleSheet('')
                self.dh6.setStyleSheet('')
                self.dh7.setStyleSheet('')
                
        if self.background_read == 'Mondstadt':
            self.original_pixmap = QPixmap(r"resource\background\Mondstadt.jpg")
            scaled_pixmap = self.original_pixmap.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.backgroundlabel.setPixmap(scaled_pixmap)
            self.backgroundlabel.setGeometry(
                (self.width() - scaled_pixmap.width()) // 2,
                (self.height() - scaled_pixmap.height()) // 2,
                scaled_pixmap.width(),
                scaled_pixmap.height()
            )

            self.setStyleSheet("QWidget#MainWindow { background-color: white; }")
            self.Label1.setStyleSheet(f'color: rgb(50, 150, 150);')
            self.yz5.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz10.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj36.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj43.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj48.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj51.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my2.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my8.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn84.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn85.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn86.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn87.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn88.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz3.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz9.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.dh1.setStyleSheet(f'background-color: rgb(50, 150, 150);')
            self.dh2.setStyleSheet(f'background-color: rgb(50, 150, 150);')
            self.dh3.setStyleSheet(f'background-color: rgb(50, 150, 150);')
            self.dh4.setStyleSheet(f'background-color: rgb(50, 150, 150);')
            self.dh5.setStyleSheet(f'background-color: rgb(50, 150, 150);')
            self.dh6.setStyleSheet(f'background-color: rgb(50, 150, 150);')
            self.dh7.setStyleSheet(f'background-color: rgb(50, 150, 150);')
            
        if self.background_read == 'Liyue':
            self.original_pixmap = QPixmap(r"resource\background\Liyue.jpg")
            scaled_pixmap = self.original_pixmap.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.backgroundlabel.setPixmap(scaled_pixmap)
            self.backgroundlabel.setGeometry(
                (self.width() - scaled_pixmap.width()) // 2,
                (self.height() - scaled_pixmap.height()) // 2,
                scaled_pixmap.width(),
                scaled_pixmap.height()
            )

            self.setStyleSheet("QWidget#MainWindow { background-color: white; }")
            self.Label1.setStyleSheet(f'color: rgb(205, 145, 70);')
            self.yz5.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz10.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj36.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj43.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj48.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj51.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my2.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my8.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn84.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn85.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn86.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn87.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn88.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz3.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz9.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.dh1.setStyleSheet(f'background-color: rgb(205, 145, 70);')
            self.dh2.setStyleSheet(f'background-color: rgb(205, 145, 70);')
            self.dh3.setStyleSheet(f'background-color: rgb(205, 145, 70);')
            self.dh4.setStyleSheet(f'background-color: rgb(205, 145, 70);')
            self.dh5.setStyleSheet(f'background-color: rgb(205, 145, 70);')
            self.dh6.setStyleSheet(f'background-color: rgb(205, 145, 70);')
            self.dh7.setStyleSheet(f'background-color: rgb(205, 145, 70);')
            
        if self.background_read == 'Inazuma':
            self.original_pixmap = QPixmap(r"resource\background\Inazuma.jpg")
            scaled_pixmap = self.original_pixmap.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.backgroundlabel.setPixmap(scaled_pixmap)
            self.backgroundlabel.setGeometry(
                (self.width() - scaled_pixmap.width()) // 2,
                (self.height() - scaled_pixmap.height()) // 2,
                scaled_pixmap.width(),
                scaled_pixmap.height()
            )

            self.setStyleSheet("QWidget#MainWindow { background-color: white; }")
            self.Label1.setStyleSheet(f'color: rgb(105, 90, 185);')
            self.yz5.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz10.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj36.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj43.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj48.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj51.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my2.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my8.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn84.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn85.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn86.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn87.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn88.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz3.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz9.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.dh1.setStyleSheet(f'background-color: rgb(105, 90, 185);')
            self.dh2.setStyleSheet(f'background-color: rgb(105, 90, 185);')
            self.dh3.setStyleSheet(f'background-color: rgb(105, 90, 185);')
            self.dh4.setStyleSheet(f'background-color: rgb(105, 90, 185);')
            self.dh5.setStyleSheet(f'background-color: rgb(105, 90, 185);')
            self.dh6.setStyleSheet(f'background-color: rgb(105, 90, 185);')
            self.dh7.setStyleSheet(f'background-color: rgb(105, 90, 185);')
            
        if self.background_read == 'Sumeru':
            self.original_pixmap = QPixmap(r"resource\background\Sumeru.jpg")
            scaled_pixmap = self.original_pixmap.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.backgroundlabel.setPixmap(scaled_pixmap)
            self.backgroundlabel.setGeometry(
                (self.width() - scaled_pixmap.width()) // 2,
                (self.height() - scaled_pixmap.height()) // 2,
                scaled_pixmap.width(),
                scaled_pixmap.height()
            )

            self.setStyleSheet("QWidget#MainWindow { background-color: white; }")
            self.Label1.setStyleSheet(f'color: rgb(105, 175, 25);')
            self.yz5.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz10.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj36.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj43.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj48.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj51.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my2.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my8.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn84.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn85.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn86.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn87.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn88.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz3.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz9.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.dh1.setStyleSheet(f'background-color: rgb(105, 175, 25);')
            self.dh2.setStyleSheet(f'background-color: rgb(105, 175, 25);')
            self.dh3.setStyleSheet(f'background-color: rgb(105, 175, 25);')
            self.dh4.setStyleSheet(f'background-color: rgb(105, 175, 25);')
            self.dh5.setStyleSheet(f'background-color: rgb(105, 175, 25);')
            self.dh6.setStyleSheet(f'background-color: rgb(105, 175, 25);')
            self.dh7.setStyleSheet(f'background-color: rgb(105, 175, 25);')
            
        if self.background_read == 'Fontaine':
            self.original_pixmap = QPixmap(r"resource\background\Fontaine.jpg")
            scaled_pixmap = self.original_pixmap.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.backgroundlabel.setPixmap(scaled_pixmap)
            self.backgroundlabel.setGeometry(
                (self.width() - scaled_pixmap.width()) // 2,
                (self.height() - scaled_pixmap.height()) // 2,
                scaled_pixmap.width(),
                scaled_pixmap.height()
            )

            self.setStyleSheet("QWidget#MainWindow { background-color: white; }")
            self.Label1.setStyleSheet(f'color: rgb(75, 145, 200);')
            self.yz5.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz10.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj36.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj43.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj48.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj51.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my2.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my8.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn84.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn85.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn86.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn87.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn88.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz3.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz9.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.dh1.setStyleSheet(f'background-color: rgb(75, 145, 200);')
            self.dh2.setStyleSheet(f'background-color: rgb(75, 145, 200);')
            self.dh3.setStyleSheet(f'background-color: rgb(75, 145, 200);')
            self.dh4.setStyleSheet(f'background-color: rgb(75, 145, 200);')
            self.dh5.setStyleSheet(f'background-color: rgb(75, 145, 200);')
            self.dh6.setStyleSheet(f'background-color: rgb(75, 145, 200);')
            self.dh7.setStyleSheet(f'background-color: rgb(75, 145, 200);')
            
        if self.background_read == 'Natlan':
            self.original_pixmap = QPixmap(r"resource\background\Natlan.jpg")
            scaled_pixmap = self.original_pixmap.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.backgroundlabel.setPixmap(scaled_pixmap)
            self.backgroundlabel.setGeometry(
                (self.width() - scaled_pixmap.width()) // 2,
                (self.height() - scaled_pixmap.height()) // 2,
                scaled_pixmap.width(),
                scaled_pixmap.height()
            )

            self.setStyleSheet("QWidget#MainWindow { background-color: white; }")
            self.Label1.setStyleSheet(f'color: rgb(235, 75, 35);')
            self.yz5.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.yz10.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj36.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj43.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj48.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.bj51.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.jy6.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my2.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.my8.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn84.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn85.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn86.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn87.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.mn88.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz1.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz3.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz4.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz7.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.sz9.setStyleSheet(f'color: rgb(255, 255, 255);')
            self.dh1.setStyleSheet(f'background-color: rgb(235, 75, 35);')
            self.dh2.setStyleSheet(f'background-color: rgb(235, 75, 35);')
            self.dh3.setStyleSheet(f'background-color: rgb(235, 75, 35);')
            self.dh4.setStyleSheet(f'background-color: rgb(235, 75, 35);')
            self.dh5.setStyleSheet(f'background-color: rgb(235, 75, 35);')
            self.dh6.setStyleSheet(f'background-color: rgb(235, 75, 35);')
            self.dh7.setStyleSheet(f'background-color: rgb(235, 75, 35);')

    def resizeEvent(self, event):
        if hasattr(self, 'original_pixmap') and not self.original_pixmap.isNull():
            self.update_background()
        super().resizeEvent(event)

    def sz2p(self, index):
        if index == 0:
            self.background_read = None
            with open(r'resource\setting\background.txt', 'w', encoding='utf-8') as file:
                file.write("")
        if index == 1:
            self.background_read = 'Mondstadt'
            with open(r'resource\setting\background.txt', 'w', encoding='utf-8') as file:
                file.write("Mondstadt")
        if index == 2:
            self.background_read = 'Liyue'
            with open(r'resource\setting\background.txt', 'w', encoding='utf-8') as file:
                file.write("Liyue")
        if index == 3:
            self.background_read = 'Inazuma'
            with open(r'resource\setting\background.txt', 'w', encoding='utf-8') as file:
                file.write("Inazuma")
        if index == 4:
            self.background_read = 'Sumeru'
            with open(r'resource\setting\background.txt', 'w', encoding='utf-8') as file:
                file.write("Sumeru")
        if index == 5:
            self.background_read = 'Fontaine'
            with open(r'resource\setting\background.txt', 'w', encoding='utf-8') as file:
                file.write("Fontaine")
        if index == 6:
            self.background_read = 'Natlan'
            with open(r'resource\setting\background.txt', 'w', encoding='utf-8') as file:
                file.write("Natlan")
        self.update_background()

    def sz6p(self):
        self.c = self.sz5.text()
        self.p = self.sz8.text()
        with open(r'resource\setting\c.txt', 'w', encoding='utf-8') as file:
            file.write(self.c)
        with open(r'resource\setting\p.txt', 'w', encoding='utf-8') as file:
            file.write(self.p)

    def sz10p(self):
        if not self.watermark:
            self.watermark = WatermarkWindow()
            self.watermark.show()
            self.sz10.setEnabled(False)
            self.sz11.setEnabled(True)

    def sz11p(self):
        if self.watermark:
            self.watermark.close()
            self.watermark = None
            self.sz10.setEnabled(True)
            self.sz11.setEnabled(False)

    def sy1p(self):
        url2 = r'https://www.bilibili.com/video/BV1yebaznEAe'
        webbrowser.open(url2)

    def sy2p(self):
        url2 = r'https://space.bilibili.com/1302740287'
        webbrowser.open(url2)

    def sy3p(self):
        sys.exit()
            
if __name__ == "__main__":
    app = QApplication(sys.argv)
    myappid = "MAGIL4.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app.setStyleSheet("""
        QPushButton {
            border-radius: 10px;
            background-color: palette(button);  /* 使用系统默认按钮颜色 */
            border: 1px solid palette(mid);      /* 使用系统默认边框颜色 */
            padding: 5px;
        }

        QPushButton:hover {
            background-color: palette(light);   /* 悬停时变亮 */
        }
        QPushButton:pressed {
            background-color: palette(dark); 
        }
    """)
    window = MainWindow.get_instance()
    window.setStyleSheet("background-color: white;")
    window.show()
    sys.exit(app.exec_())
