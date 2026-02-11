import tkinter as tk
from customtkinter import CTkFrame, CTkLabel, CTkEntry, CTkButton, CTkTextbox

class FinanceCalendar(CTkFrame):
    def __init__(self, master=None):
        super().__init__(master)
        self.initialize_ui()

    def initialize_ui(self):
        self.grid()
        self.create_widgets()

    def create_widgets(self):
        self.label = CTkLabel(self, text="Welcome to Finance Calendar")
        self.label.grid(row=0, column=0, padx=10, pady=10)

        self.entry = CTkEntry(self)
        self.entry.grid(row=1, column=0, padx=10, pady=10)

        self.save_button = CTkButton(self, text="Save", command=self.save_entry)
        self.save_button.grid(row=2, column=0, padx=10, pady=10)

        self.textbox = CTkTextbox(self, width=50, height=10)
        self.textbox.grid(row=3, column=0, padx=10, pady=10)

    def save_entry(self):
        entry_text = self.entry.get()
        if entry_text:
            self.textbox.insert(tk.END, entry_text + "\n")
            self.entry.delete(0, tk.END)

if __name__ == '__main__':
    root = tk.Tk()
    app = FinanceCalendar(master=root)
    app.mainloop()