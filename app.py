"""ClearDesk: a Windows-friendly, offline document scanner."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from PIL import Image, ImageTk
from scanner import enhance, export_pdf, load_image


@dataclass
class Page:
    name: str
    image: Image.Image


class App:
    def __init__(self, root):
        self.root = root
        self.pages = []
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.busy = False
        self.crop_start = None
        self.crop_rect = None
        self.preview_image = None
        root.title('ClearDesk — Document Scanner')
        root.geometry('1100x760')
        root.minsize(850, 600)
        root.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', padding=7)
        top = ttk.Frame(root, padding=12)
        top.pack(fill='x')
        ttk.Label(top, text='ClearDesk', font=('Segoe UI', 21, 'bold')).pack(side='left')
        ttk.Label(top, text='   Photos → clean documents → PDF').pack(side='left')
        self.controls = []
        self.button(top, 'Export PDF', self.export).pack(side='right')
        self.button(top, 'Import images', self.import_images).pack(side='right', padx=8)
        body = ttk.Frame(root, padding=(12, 0))
        body.pack(fill='both', expand=True)
        side = ttk.Frame(body, width=220)
        side.pack(side='left', fill='y', padx=(0, 12))
        ttk.Label(side, text='PAGES', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        self.listbox = tk.Listbox(side, width=26, exportselection=False, font=('Segoe UI', 10))
        self.listbox.pack(fill='both', expand=True, pady=8)
        self.listbox.bind('<<ListboxSelect>>', lambda _: self.preview())
        for title, action in [('Move up', lambda: self.move(-1)), ('Move down', lambda: self.move(1)), ('Rotate 90°', self.rotate), ('Remove page', self.remove)]:
            self.button(side, title, action).pack(fill='x', pady=2)
        settings = ttk.Frame(side)
        settings.pack(fill='x', pady=12)
        ttk.Label(settings, text='Cleanup (applies to all pages)').pack(anchor='w')
        self.mode = tk.StringVar(value='Clean gray')
        menu = ttk.Combobox(settings, textvariable=self.mode, state='readonly', values=['Clean gray', 'Black & white', 'Original'], width=24)
        menu.pack(fill='x', pady=6)
        menu.bind('<<ComboboxSelected>>', lambda _: self.preview())
        self.controls.append(menu)
        ttk.Label(settings, text='Shadow removal strength').pack(anchor='w')
        self.strength = tk.IntVar(value=75)
        scale = tk.Scale(settings, from_=0, to=100, orient='horizontal', variable=self.strength, command=lambda _: self.schedule_preview())
        scale.pack(fill='x')
        self.controls.append(scale)
        self.original = tk.BooleanVar()
        ttk.Checkbutton(settings, text='Preview original', variable=self.original, command=self.preview).pack(anchor='w', pady=6)
        ttk.Label(settings, text='PDF paper size').pack(anchor='w')
        self.paper = tk.StringVar(value='A4')
        ttk.Combobox(settings, textvariable=self.paper, state='readonly', values=['A4', 'Letter', 'Image size'], width=24).pack(fill='x', pady=6)
        self.canvas = tk.Canvas(body, background='#28313d', highlightthickness=0)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda _: self.schedule_preview())
        self.canvas.bind('<ButtonPress-1>', self.crop_begin)
        self.canvas.bind('<B1-Motion>', self.crop_drag)
        self.canvas.bind('<ButtonRelease-1>', self.crop_end)
        self.status = tk.StringVar(value='Import JPG, PNG, BMP, TIFF or WebP images. Drag on the preview to crop a page.')
        ttk.Label(root, textvariable=self.status, padding=12).pack(fill='x')
        self.pending = None
        self.preview()

    def button(self, parent, title, action):
        widget = ttk.Button(parent, text=title, command=action)
        self.controls.append(widget)
        return widget

    def selected(self):
        selection = self.listbox.curselection()
        return selection[0] if selection else None

    def refresh(self, index=0):
        self.listbox.delete(0, 'end')
        for i, page in enumerate(self.pages):
            self.listbox.insert('end', f'{i + 1}. {page.name}')
        if self.pages:
            self.listbox.selection_set(min(index, len(self.pages) - 1))
        self.preview()

    def run_job(self, work, done):
        if self.busy:
            return
        self.busy = True
        for widget in self.controls:
            widget.configure(state='disabled')
        future = self.pool.submit(work)
        def poll():
            if not future.done():
                self.root.after(80, poll)
                return
            self.busy = False
            for widget in self.controls:
                widget.configure(state='readonly' if isinstance(widget, ttk.Combobox) else 'normal')
            try:
                done(future.result())
            except Exception as exc:
                self.status.set('Operation failed. Your original files have not been changed.')
                messagebox.showerror('ClearDesk', str(exc))
        self.root.after(80, poll)

    def import_images(self):
        paths = filedialog.askopenfilenames(filetypes=[('Images', '*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp')])
        if not paths:
            return
        self.status.set('Loading images…')
        def load():
            from pathlib import Path
            pages, errors = [], []
            for path in paths:
                try:
                    pages.append(Page(Path(path).name, load_image(path)))
                except Exception as exc:
                    errors.append(f'{Path(path).name}: {exc}')
            return pages, errors
        def done(result):
            pages, errors = result
            self.pages.extend(pages)
            self.refresh(len(self.pages) - 1)
            self.status.set(f'Imported {len(pages)} page(s). Drag on the preview to crop.')
            if errors:
                messagebox.showwarning('Some images could not be imported', '\n'.join(errors))
        self.run_job(load, done)

    def schedule_preview(self):
        if self.pending:
            self.root.after_cancel(self.pending)
        self.pending = self.root.after(100, self.preview)

    def preview(self):
        self.pending = None
        self.canvas.delete('all')
        self.crop_start = None
        index = self.selected()
        if index is None:
            self.canvas.create_text(max(self.canvas.winfo_width(), 400) // 2, 180, text='Import document photos to get started', fill='white', font=('Segoe UI', 16))
            self.preview_image = None
            return
        image = self.pages[index].image.copy()
        image.thumbnail((max(50, self.canvas.winfo_width() - 40), max(50, self.canvas.winfo_height() - 40)))
        if not self.original.get():
            image = enhance(image, self.mode.get(), self.strength.get())
        self.preview_image = ImageTk.PhotoImage(image)
        self.offset = ((self.canvas.winfo_width() - image.width) // 2, (self.canvas.winfo_height() - image.height) // 2)
        self.canvas.create_image(*self.offset, image=self.preview_image, anchor='nw')

    def move(self, delta):
        i = self.selected()
        if i is not None and 0 <= i + delta < len(self.pages):
            self.pages[i], self.pages[i + delta] = self.pages[i + delta], self.pages[i]
            self.refresh(i + delta)

    def rotate(self):
        i = self.selected()
        if i is not None:
            self.pages[i].image = self.pages[i].image.transpose(Image.Transpose.ROTATE_270)
            self.preview()

    def remove(self):
        i = self.selected()
        if i is not None:
            self.pages.pop(i)
            self.refresh(i)

    def crop_point(self, event):
        x, y = self.offset
        return (max(x, min(event.x, x + self.preview_image.width())), max(y, min(event.y, y + self.preview_image.height())))

    def crop_begin(self, event):
        if self.busy or self.preview_image is None:
            return
        self.crop_start = self.crop_point(event)
        self.crop_rect = self.canvas.create_rectangle(*self.crop_start, *self.crop_start, outline='#64caff', width=2)

    def crop_drag(self, event):
        if self.crop_start:
            self.canvas.coords(self.crop_rect, *self.crop_start, *self.crop_point(event))

    def crop_end(self, event):
        if not self.crop_start:
            return
        a, b = self.crop_start, self.crop_point(event)
        self.crop_start = None
        self.canvas.delete(self.crop_rect)
        if abs(a[0] - b[0]) < 15 or abs(a[1] - b[1]) < 15:
            return
        if not messagebox.askyesno('Crop page', 'Keep only the selected area? You can reimport the original to reset.'):
            return
        image = self.pages[self.selected()].image
        x, y = self.offset
        sx, sy = image.width / self.preview_image.width(), image.height / self.preview_image.height()
        box = (round((min(a[0], b[0]) - x) * sx), round((min(a[1], b[1]) - y) * sy), round((max(a[0], b[0]) - x) * sx), round((max(a[1], b[1]) - y) * sy))
        self.pages[self.selected()].image = image.crop(box)
        self.preview()

    def export(self):
        if not self.pages:
            messagebox.showinfo('Export PDF', 'Import at least one image first.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('PDF document', '*.pdf')])
        if not path:
            return
        mode, strength, paper = self.mode.get(), self.strength.get(), self.paper.get()
        images = [page.image for page in self.pages]
        self.status.set('Cleaning full-resolution pages and exporting PDF…')
        def work():
            processed = [enhance(image, mode, strength) for image in images]
            try:
                export_pdf(processed, path, paper)
            finally:
                for image in processed:
                    image.close()
        self.run_job(work, lambda _: self.status.set(f'Saved {len(images)} pages to {path}'))

    def close(self):
        if self.busy:
            messagebox.showinfo('Please wait', 'Wait for the current operation to finish before closing.')
            return
        self.pool.shutdown(wait=False)
        self.root.destroy()


if __name__ == '__main__':
    App(tk.Tk()).root.mainloop()
