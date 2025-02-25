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
    # Modified to include shift key state
    deleteClicked = pyqtSignal(str, bool)
    
    def __init__(self, title, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.title = title
        
        # Set fixed height to ensure visibility
        self.setMinimumHeight(36)
        
        # Create main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(0)
        
        # Create title label that takes full width
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 10))
        self.title_label.setStyleSheet("color: #e6e6e6; background: transparent;")
        
        # Add label to layout with stretch to take full width
        layout.addWidget(self.title_label, 1)
        
        # Create delete button with overlay capability
        self.delete_button = QToolButton(self)
        self.delete_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        # Make icon larger
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
        
        # Truncate long titles with ellipsis
        self.update_title_display()
        
        # Position button after layout is set
        self.resizeEvent(None)
    
    def handle_delete_click(self):
        # Get the shift key state and pass it with the signal
        modifiers = QApplication.keyboardModifiers()
        shift_pressed = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        self.deleteClicked.emit(self.filepath, shift_pressed)
    
    def update_title_display(self):
        metrics = QFontMetrics(self.title_label.font())
        # Leave space at the end for the delete button
        available_width = self.width() - 50
        if available_width > 0:
            elided_text = metrics.elidedText(self.title, Qt.TextElideMode.ElideRight, available_width)
            self.title_label.setText(elided_text)
    
    def resizeEvent(self, event):
        # Position the delete button to overlay title area on the right
        # but not too close to the edge
        btn_x = self.width() - self.delete_button.width() - 15
        btn_y = (self.height() - self.delete_button.height()) // 2
        self.delete_button.move(QPoint(btn_x, btn_y))
        
        # Update truncation when widget size changes
        self.update_title_display()
        if event:
            super().resizeEvent(event)

class CustomListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Performance optimization: minimal updates
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(True)  # Performance optimization when all items are similar size
    
    def mouseReleaseEvent(self, event):
        # This helps ensure the custom item widgets receive events
        super().mouseReleaseEvent(event)
        
        # Get the item at the position
        item = self.itemAt(event.position().toPoint())
        if item:
            # Re-trigger the current item
            self.setCurrentItem(item)

class NoteApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # App configuration
        self.notes_dir = os.path.join(os.path.expanduser("~"), "QuickNotes")
        self.current_note = None
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.save_current_note)
        self.autosave_timer.start(1000)  # Autosave every second
        self.is_new_note_mode = False
        
        # Performance optimization: cache loaded note data
        self.note_cache = {}
        
        # Ensure the notes directory exists
        if not os.path.exists(self.notes_dir):
            os.makedirs(self.notes_dir)
            
        # Set up the UI
        self.setup_ui()
        
        # Load existing notes
        self.load_notes()
        
        # Create a new note on startup
        self.create_new_note()
    
    def setup_ui(self):
        self.setWindowTitle("QuickNote")
        self.setMinimumSize(800, 500)
        
        # Set up dark mode
        self.set_dark_theme()
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Sidebar (left panel)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(10)
        
        # Notes list header
        sidebar_header = QWidget()
        header_layout = QHBoxLayout(sidebar_header)
        header_layout.setContentsMargins(0, 5, 0, 15)
        
        sidebar_label = QLabel("Notes")
        sidebar_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        
        header_layout.addWidget(sidebar_label)
        header_layout.addStretch()
        
        # Notes list - using custom list widget for better event handling
        self.notes_list = CustomListWidget()
        self.notes_list.setObjectName("notesList")
        self.notes_list.setFrameShape(QFrame.Shape.NoFrame)
        self.notes_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.notes_list.setSpacing(2)  # Add spacing between items
        self.notes_list.currentItemChanged.connect(self.load_selected_note)
        
        # New note button
        new_note_btn = QPushButton("+ New Note")
        new_note_btn.setObjectName("newNoteButton")
        new_note_btn.setFont(QFont("Segoe UI", 10))
        new_note_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_note_btn.clicked.connect(self.create_new_note)
        
        # Add widgets to sidebar
        sidebar_layout.addWidget(sidebar_header)
        sidebar_layout.addWidget(self.notes_list)
        sidebar_layout.addWidget(new_note_btn)
        
        # Divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setObjectName("divider")
        
        # Note editor (right panel)
        editor_panel = QWidget()
        editor_panel.setObjectName("editorPanel")
        self.editor_layout = QVBoxLayout(editor_panel)
        self.editor_layout.setContentsMargins(25, 20, 25, 20)
        self.editor_layout.setSpacing(15)
        
        # Note title
        self.title_label = QLabel("New Note")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        
        # Title input for new notes (initially hidden)
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
        
        # Stack widget to switch between title input and content
        self.editor_stack = QStackedWidget()
        
        # Content widget
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Note editor
        self.note_editor = QTextEdit()
        self.note_editor.setObjectName("noteEditor")
        self.note_editor.setFont(QFont("Segoe UI", 11))
        self.note_editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.note_editor.setFrameShape(QFrame.Shape.NoFrame)
        # Performance optimization: use a timer for text changes
        self.editor_change_timer = QTimer()
        self.editor_change_timer.setSingleShot(True)
        self.editor_change_timer.timeout.connect(self.handle_editor_change)
        self.note_editor.textChanged.connect(self.on_text_changed)
        
        content_layout.addWidget(self.note_editor)
        
        # Add widgets to stack
        self.editor_stack.addWidget(self.title_input_container)  # Index 0: Title input
        self.editor_stack.addWidget(self.content_widget)         # Index 1: Note content
        
        # Add widgets to editor layout
        self.editor_layout.addWidget(self.title_label)
        self.editor_layout.addWidget(self.editor_stack)
        
        # Add widgets to main layout
        main_layout.addWidget(sidebar)
        main_layout.addWidget(divider)
        main_layout.addWidget(editor_panel, 1)  # Editor takes more space
        
        self.setCentralWidget(main_widget)
    
    def on_text_changed(self):
        # Debounce the text change events for better performance
        self.editor_change_timer.start(300)
    
    def handle_editor_change(self):
        # This will be called only after the user stops typing for 300ms
        if self.current_note:
            pass  # The autosave timer will handle saving
    
    def set_dark_theme(self):
        # Dark theme colors
        dark_palette = QPalette()
        
        dark_bg = QColor(30, 30, 30)
        sidebar_bg = QColor(25, 25, 25)
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
        
        # Apply the palette
        QApplication.setPalette(dark_palette)
        
        # Set stylesheet for additional styling
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
    
    # Modified to accept shift key state
    def delete_note(self, filepath, shift_pressed=False):
        # Skip confirmation if shift is pressed
        if shift_pressed:
            self.perform_delete(filepath)
            return
            
        # Ask for confirmation only if shift is not pressed
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
            # If the current note is being deleted, clear the editor
            if self.current_note == filepath:
                self.current_note = None
                self.title_label.setText("Note Deleted")
                self.note_editor.clear()
            
            # Delete the file
            os.remove(filepath)
            
            # Remove from cache for performance
            if filepath in self.note_cache:
                del self.note_cache[filepath]
            
            # Reload notes list
            self.load_notes()
            
            # If there are other notes, select the first one
            if self.notes_list.count() > 0:
                self.notes_list.setCurrentRow(0)
            else:
                # If no notes remain, go to new note mode
                self.create_new_note()
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not delete note: {str(e)}")
    
    def create_new_note(self):
        # Set up for new note creation
        self.title_label.setText("Create New Note")
        self.is_new_note_mode = True
        self.current_note = None
        
        # Switch to title input view
        self.editor_stack.setCurrentIndex(0)
        
        # Clear the title input and set focus
        self.title_input.clear()
        self.title_input.setFocus()
        
        # Deselect any selected note
        self.notes_list.clearSelection()
    
    def confirm_new_note(self):
        title = self.title_input.text().strip()
        
        if not title:
            return  # Don't create notes without a title
        
        # Generate a filename based on the title and timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{title.replace(' ', '_')}.json"
        filepath = os.path.join(self.notes_dir, filename)
        
        # Create a new note structure
        note_data = {
            "title": title,
            "content": "",
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat()
        }
        
        # Save the new note
        with open(filepath, 'w') as f:
            json.dump(note_data, f)
        
        # Add to cache for better performance
        self.note_cache[filepath] = note_data
        
        # Update the notes list
        self.load_notes()
        
        # Switch to editor view
        self.editor_stack.setCurrentIndex(1)
        self.is_new_note_mode = False
        
        # Set note as current and update title
        self.title_label.setText(title)
        self.current_note = filepath
        
        # Select the new note in the list
        for i in range(self.notes_list.count()):
            if self.notes_list.item(i).data(Qt.ItemDataRole.UserRole) == filepath:
                self.notes_list.setCurrentRow(i)
                break
        
        # Clear the editor and set focus
        self.note_editor.clear()
        self.note_editor.setFocus()
    
    def load_notes(self):
        # Performance optimization: save selection before clearing
        current_path = None
        if self.notes_list.currentItem():
            current_path = self.notes_list.currentItem().data(Qt.ItemDataRole.UserRole)
        
        self.notes_list.clear()
        
        # Get all JSON files in the notes directory
        note_files = [f for f in os.listdir(self.notes_dir) if f.endswith('.json')]
        note_files.sort(reverse=True)  # Most recent first
        
        # Batch load notes for better performance
        for note_file in note_files:
            filepath = os.path.join(self.notes_dir, note_file)
            try:
                # Check if already in cache first for performance
                if filepath in self.note_cache:
                    note_data = self.note_cache[filepath]
                else:
                    with open(filepath, 'r') as f:
                        note_data = json.load(f)
                    # Add to cache
                    self.note_cache[filepath] = note_data
                
                # Add to the list using custom widget
                title = note_data.get('title', 'Untitled')
                
                # Create the list item first
                item = QListWidgetItem()
                # Set a minimum height to ensure visibility
                item.setSizeHint(QSize(200, 40))
                item.setData(Qt.ItemDataRole.UserRole, filepath)
                
                # Create the custom widget with the trash icon
                item_widget = NoteItemWidget(title, filepath)
                item_widget.deleteClicked.connect(self.delete_note)
                
                # Add the item to the list first, then set the widget
                self.notes_list.addItem(item)
                self.notes_list.setItemWidget(item, item_widget)
                
            except Exception as e:
                print(f"Error loading note {note_file}: {e}")
        
        # Restore selection if possible
        if current_path:
            for i in range(self.notes_list.count()):
                if self.notes_list.item(i).data(Qt.ItemDataRole.UserRole) == current_path:
                    self.notes_list.setCurrentRow(i)
                    break
    
    def load_selected_note(self, current, previous):
        if not current:
            return
        
        # Performance optimization: don't reload if it's already the current note
        filepath = current.data(Qt.ItemDataRole.UserRole)
        if self.current_note == filepath:
            return
            
        # Always cancel new note mode if a note is selected
        if self.is_new_note_mode:
            self.is_new_note_mode = False
            # Switch to content view
            self.editor_stack.setCurrentIndex(1)
        
        try:
            # Check cache first for performance
            if filepath in self.note_cache:
                note_data = self.note_cache[filepath]
            else:
                with open(filepath, 'r') as f:
                    note_data = json.load(f)
                # Add to cache
                self.note_cache[filepath] = note_data
            
            # Block signals temporarily for performance
            self.note_editor.blockSignals(True)
            self.title_label.setText(note_data.get('title', 'Untitled'))
            self.note_editor.setText(note_data.get('content', ''))
            self.note_editor.blockSignals(False)
            self.current_note = filepath
            
        except Exception as e:
            print(f"Error loading note: {e}")
    
    def note_content_changed(self):
        if self.current_note:
            # The autosave timer will take care of saving
            pass
    
    def save_current_note(self):
        if not self.current_note:
            return
        
        try:
            # Get current content
            current_content = self.note_editor.toPlainText()
            
            # Check if content has actually changed before saving
            if self.current_note in self.note_cache:
                if self.note_cache[self.current_note].get('content') == current_content:
                    return  # No changes to save
            
            # Load the current note data
            if self.current_note in self.note_cache:
                note_data = self.note_cache[self.current_note]
            else:
                with open(self.current_note, 'r') as f:
                    note_data = json.load(f)
            
            # Update the content and timestamp
            note_data['content'] = current_content
            note_data['updated'] = datetime.now().isoformat()
            
            # Update the cache
            self.note_cache[self.current_note] = note_data
            
            # Save back to file
            with open(self.current_note, 'w') as f:
                json.dump(note_data, f)
                
        except Exception as e:
            print(f"Error saving note: {e}")
    
    def closeEvent(self, event):
        # Save the current note before closing
        self.save_current_note()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = NoteApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
