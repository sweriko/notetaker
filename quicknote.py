import sys
import os
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTextEdit, QListWidget, QLineEdit, QLabel, QPushButton, QFrame,
    QSizePolicy, QStackedWidget, QToolButton, QListWidgetItem, QStyle, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QPoint
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QFontMetrics

class NoteItemWidget(QWidget):
    deleteClicked = pyqtSignal(str, bool)
    
    def __init__(self, title, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.title = title
        
        self.setMinimumHeight(36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(0)
        
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 10))
        self.title_label.setStyleSheet("color: #e6e6e6; background: transparent;")
        layout.addWidget(self.title_label, 1)
        
        self.delete_button = QToolButton(self)
        self.delete_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.delete_button.setIconSize(QSize(18, 18))
        self.delete_button.setFixedSize(QSize(28, 28))
        self.delete_button.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: rgba(40, 40, 40, 0.8);
                border-radius: 14px;
            }
            QToolButton:hover {
                background-color: rgba(255, 70, 70, 0.85);
            }
        """)
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.clicked.connect(self.handle_delete_click)
        
        self.update_title_display()
        self.resizeEvent(None)
    
    def handle_delete_click(self):
        modifiers = QApplication.keyboardModifiers()
        shift_pressed = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        self.deleteClicked.emit(self.filepath, shift_pressed)
    
    def update_title_display(self):
        metrics = QFontMetrics(self.title_label.font())
        available_width = self.width() - 50
        if available_width > 0:
            elided_text = metrics.elidedText(self.title, Qt.TextElideMode.ElideRight, available_width)
            self.title_label.setText(elided_text)
    
    def resizeEvent(self, event):
        btn_x = self.width() - self.delete_button.width() - 15
        btn_y = (self.height() - self.delete_button.height()) // 2
        self.delete_button.move(QPoint(btn_x, btn_y))
        self.update_title_display()
        if event:
            super().resizeEvent(event)

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(True)
    
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        item = self.itemAt(event.position().toPoint())
        if item:
            self.setCurrentItem(item)

class NoteApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(r"C:\Users\erase\notetaker\quicknoteapp.ico"))
        
        self.notes_dir = os.path.join(os.path.expanduser("~"), "QuickNotes")
        self.current_note = None
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.save_current_note)
        self.autosave_timer.start(1000)  # Autosave every second
        self.is_new_note_mode = False
        self.note_cache = {}
        
        if not os.path.exists(self.notes_dir):
            os.makedirs(self.notes_dir)
            
        self.setup_ui()
        # Defer loading notes slightly so the UI appears immediately.
        QTimer.singleShot(0, self.load_notes)
        self.create_new_note()
    
    def setup_ui(self):
        self.setWindowTitle("QuickNote")
        self.setMinimumSize(800, 500)
        self.set_dark_theme()
        
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(10)
        
        sidebar_header = QWidget()
        header_layout = QHBoxLayout(sidebar_header)
        header_layout.setContentsMargins(0, 5, 0, 15)
        
        sidebar_label = QLabel("Notes")
        sidebar_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header_layout.addWidget(sidebar_label)
        header_layout.addStretch()
        
        self.notes_list = CustomListWidget()
        self.notes_list.setObjectName("notesList")
        self.notes_list.setFrameShape(QFrame.Shape.NoFrame)
        self.notes_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.notes_list.setSpacing(2)
        self.notes_list.currentItemChanged.connect(self.load_selected_note)
        
        new_note_btn = QPushButton("+ New Note")
        new_note_btn.setObjectName("newNoteButton")
        new_note_btn.setFont(QFont("Segoe UI", 10))
        new_note_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_note_btn.clicked.connect(self.create_new_note)
        
        sidebar_layout.addWidget(sidebar_header)
        sidebar_layout.addWidget(self.notes_list)
        sidebar_layout.addWidget(new_note_btn)
        
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setObjectName("divider")
        
        editor_panel = QWidget()
        editor_panel.setObjectName("editorPanel")
        self.editor_layout = QVBoxLayout(editor_panel)
        self.editor_layout.setContentsMargins(25, 20, 25, 20)
        self.editor_layout.setSpacing(15)
        
        self.title_label = QLabel("New Note")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        
        self.title_input_container = QWidget()
        title_input_layout = QVBoxLayout(self.title_input_container)
        title_input_layout.setContentsMargins(0, 0, 0, 10)
        
        title_prompt = QLabel("Enter note title:")
        title_prompt.setFont(QFont("Segoe UI", 12))
        
        self.title_input = QLineEdit()
        self.title_input.setObjectName("titleInput")
        self.title_input.setFont(QFont("Segoe UI", 13))
        self.title_input.setPlaceholderText("Note title...")
        self.title_input.returnPressed.connect(self.confirm_new_note)
        
        title_input_layout.addWidget(title_prompt)
        title_input_layout.addWidget(self.title_input)
        
        self.editor_stack = QStackedWidget()
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        self.note_editor = QTextEdit()
        self.note_editor.setObjectName("noteEditor")
        self.note_editor.setFont(QFont("Segoe UI", 11))
        self.note_editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.note_editor.setFrameShape(QFrame.Shape.NoFrame)
        self.editor_change_timer = QTimer()
        self.editor_change_timer.setSingleShot(True)
        self.editor_change_timer.timeout.connect(self.handle_editor_change)
        self.note_editor.textChanged.connect(self.on_text_changed)
        
        content_layout.addWidget(self.note_editor)
        self.editor_stack.addWidget(self.title_input_container)
        self.editor_stack.addWidget(self.content_widget)
        
        self.editor_layout.addWidget(self.title_label)
        self.editor_layout.addWidget(self.editor_stack)
        
        main_layout.addWidget(sidebar)
        main_layout.addWidget(divider)
        main_layout.addWidget(editor_panel, 1)
        
        self.setCentralWidget(main_widget)
    
    def on_text_changed(self):
        self.editor_change_timer.start(300)
    
    def handle_editor_change(self):
        if self.current_note:
            # Autosave is handled by the timer
            pass
    
    def set_dark_theme(self):
        dark_palette = QPalette()
        dark_bg = QColor(30, 30, 30)
        text_color = QColor(230, 230, 230)
        highlight_color = QColor(75, 136, 255)
        
        dark_palette.setColor(QPalette.ColorRole.Window, dark_bg)
        dark_palette.setColor(QPalette.ColorRole.WindowText, text_color)
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, dark_bg)
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(42, 42, 42))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
        dark_palette.setColor(QPalette.ColorRole.Text, text_color)
        dark_palette.setColor(QPalette.ColorRole.Button, dark_bg)
        dark_palette.setColor(QPalette.ColorRole.ButtonText, text_color)
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark_palette.setColor(QPalette.ColorRole.Link, highlight_color)
        dark_palette.setColor(QPalette.ColorRole.Highlight, highlight_color)
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        
        QApplication.setPalette(dark_palette)
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #e6e6e6;
            }
            
            #sidebar {
                background-color: #191919;
                border: none;
            }
            
            #divider {
                color: #333333;
            }
            
            #notesList {
                background-color: transparent;
                border: none;
                outline: none;
                padding: 5px;
            }
            
            #notesList::item {
                background-color: transparent;
                border-radius: 4px;
                padding: 0px;
                margin-bottom: 2px;
            }
            
            #notesList::item:selected {
                background-color: #404040;
                border: none;
            }
            
            #notesList::item:hover:!selected {
                background-color: #2d2d2d;
            }
            
            #titleLabel {
                color: #e6e6e6;
            }
            
            #noteEditor, #titleInput {
                background-color: #2a2a2a;
                border: none;
                border-radius: 4px;
                padding: 10px;
                color: #e6e6e6;
            }
            
            #noteEditor {
                padding: 15px;
            }
            
            #newNoteButton {
                background-color: #4b88ff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                font-weight: bold;
            }
            
            #newNoteButton:hover {
                background-color: #3a77ee;
            }
            
            #newNoteButton:pressed {
                background-color: #2966dd;
            }
            
            QScrollBar:vertical {
                border: none;
                background: #2a2a2a;
                width: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background: #4d4d4d;
                min-height: 20px;
                border-radius: 5px;
            }
            
            QScrollBar::handle:vertical:hover {
                background: #5a5a5a;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
    
    def delete_note(self, filepath, shift_pressed=False):
        if shift_pressed:
            self.perform_delete(filepath)
            return
            
        confirm = QMessageBox.question(
            self,
            "Delete Note",
            "Are you sure you want to delete this note? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.perform_delete(filepath)
    
    def perform_delete(self, filepath):
        try:
            if self.current_note == filepath:
                self.current_note = None
                self.title_label.setText("Note Deleted")
                self.note_editor.clear()
            
            os.remove(filepath)
            if filepath in self.note_cache:
                del self.note_cache[filepath]
            
            self.load_notes()
            
            if self.notes_list.count() > 0:
                self.notes_list.setCurrentRow(0)
            else:
                self.create_new_note()
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not delete note: {str(e)}")
    
    def create_new_note(self):
        self.title_label.setText("Create New Note")
        self.is_new_note_mode = True
        self.current_note = None
        self.editor_stack.setCurrentIndex(0)
        self.title_input.clear()
        self.title_input.setFocus()
        self.notes_list.clearSelection()
    
    def confirm_new_note(self):
        title = self.title_input.text().strip()
        if not title:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{title.replace(' ', '_')}.json"
        filepath = os.path.join(self.notes_dir, filename)
        
        note_data = {
            "title": title,
            "content": "",
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(note_data, f)
        
        self.note_cache[filepath] = note_data
        self.load_notes()
        self.editor_stack.setCurrentIndex(1)
        self.is_new_note_mode = False
        self.title_label.setText(title)
        self.current_note = filepath
        
        for i in range(self.notes_list.count()):
            if self.notes_list.item(i).data(Qt.ItemDataRole.UserRole) == filepath:
                self.notes_list.setCurrentRow(i)
                break
        
        self.note_editor.clear()
        self.note_editor.setFocus()
    
    def load_notes(self):
        current_path = None
        if self.notes_list.currentItem():
            current_path = self.notes_list.currentItem().data(Qt.ItemDataRole.UserRole)
        
        self.notes_list.clear()
        note_files = []
        # Using os.scandir for faster directory traversal
        with os.scandir(self.notes_dir) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.endswith('.json'):
                    note_files.append(entry.name)
        note_files.sort(reverse=True)
        
        for note_file in note_files:
            filepath = os.path.join(self.notes_dir, note_file)
            try:
                if filepath in self.note_cache:
                    note_data = self.note_cache[filepath]
                else:
                    with open(filepath, 'r') as f:
                        note_data = json.load(f)
                    self.note_cache[filepath] = note_data
                
                title = note_data.get('title', 'Untitled')
                item = QListWidgetItem()
                item.setSizeHint(QSize(200, 40))
                item.setData(Qt.ItemDataRole.UserRole, filepath)
                
                item_widget = NoteItemWidget(title, filepath)
                item_widget.deleteClicked.connect(self.delete_note)
                
                self.notes_list.addItem(item)
                self.notes_list.setItemWidget(item, item_widget)
                
            except Exception as e:
                print(f"Error loading note {note_file}: {e}")
        
        if current_path:
            for i in range(self.notes_list.count()):
                if self.notes_list.item(i).data(Qt.ItemDataRole.UserRole) == current_path:
                    self.notes_list.setCurrentRow(i)
                    break
    
    def load_selected_note(self, current, previous):
        if not current:
            return
        
        filepath = current.data(Qt.ItemDataRole.UserRole)
        if self.current_note == filepath:
            return
            
        if self.is_new_note_mode:
            self.is_new_note_mode = False
            self.editor_stack.setCurrentIndex(1)
        
        try:
            if filepath in self.note_cache:
                note_data = self.note_cache[filepath]
            else:
                with open(filepath, 'r') as f:
                    note_data = json.load(f)
                self.note_cache[filepath] = note_data
            
            self.note_editor.blockSignals(True)
            self.title_label.setText(note_data.get('title', 'Untitled'))
            self.note_editor.setText(note_data.get('content', ''))
            self.note_editor.blockSignals(False)
            self.current_note = filepath
            
        except Exception as e:
            print(f"Error loading note: {e}")
    
    def save_current_note(self):
        if not self.current_note:
            return
        
        try:
            current_content = self.note_editor.toPlainText()
            if self.current_note in self.note_cache:
                if self.note_cache[self.current_note].get('content') == current_content:
                    return
            
            if self.current_note in self.note_cache:
                note_data = self.note_cache[self.current_note]
            else:
                with open(self.current_note, 'r') as f:
                    note_data = json.load(f)
            
            note_data['content'] = current_content
            note_data['updated'] = datetime.now().isoformat()
            self.note_cache[self.current_note] = note_data
            
            with open(self.current_note, 'w') as f:
                json.dump(note_data, f)
                
        except Exception as e:
            print(f"Error saving note: {e}")
    
    def closeEvent(self, event):
        self.save_current_note()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(r"C:\Users\erase\notetaker\quicknoteapp.ico"))
    window = NoteApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
