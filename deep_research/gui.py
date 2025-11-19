import sys
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
import os

from .config import GEMINI_KEY, BRAVE_API_KEY, UNPAYWALL_EMAIL, JOURNAL_H_INDEX_THRESHOLD, OUTPUT_FILE
from .core import generate_keywords, filter_snippets, save_bibliometrics, synthesise
from .search import search_all
from .utils import build_doc, safe_save, logger

import queue
import logging

class QueueHandler(logging.Handler):
    """Log handler that writes to a queue."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(record)

class GUILogger:
    """Legacy wrapper for print redirection if needed, but we use logging now."""
    def __init__(self, log_queue):
        self.log_queue = log_queue
        
    def write(self, message):
        if message and message.strip():
            self.log_queue.put(logging.makeLogRecord({'msg': message, 'levelno': logging.INFO}))
            
    def flush(self):
        pass

class ResearchGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Deep Research Tool - v5.0")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        self.subject_var = tk.StringVar()
        self.general_var = tk.IntVar(value=3)
        self.academic_var = tk.IntVar(value=2)
        self.is_running = False
        self.stop_event = threading.Event()
        self.log_queue = queue.Queue()
        
        self.setup_ui()
        self.poll_log_queue()
        
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Label(header_frame, text="🔬 Deep Research Tool", font=("Arial", 18, "bold")).pack(side=tk.LEFT)
        
        # Input
        input_frame = ttk.LabelFrame(main_frame, text="Research Parameters", padding="10")
        input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)
        
        ttk.Label(input_frame, text="Subject:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(input_frame, textvariable=self.subject_var, width=60).grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        
        param_frame = ttk.Frame(input_frame)
        param_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Label(param_frame, text="General Queries:").pack(side=tk.LEFT)
        ttk.Spinbox(param_frame, from_=1, to=10, textvariable=self.general_var, width=5).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(param_frame, text="Academic Queries:").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Spinbox(param_frame, from_=0, to=10, textvariable=self.academic_var, width=5).pack(side=tk.LEFT, padx=5)
        
        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=0, column=2, rowspan=2, padx=10)
        
        self.start_btn = ttk.Button(btn_frame, text="🚀 Start", command=self.start_research)
        self.start_btn.pack(fill=tk.X, pady=2)
        
        self.stop_btn = ttk.Button(btn_frame, text="🛑 Stop", command=self.stop_research, state='disabled')
        self.stop_btn.pack(fill=tk.X, pady=2)
        
        # Logs
        log_frame = ttk.LabelFrame(main_frame, text="Logs", padding="5")
        log_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, state='disabled', font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Progress
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
    def start_research(self):
        if not self.subject_var.get():
            messagebox.showwarning("Error", "Please enter a subject")
            return
            
        self.is_running = True
        self.stop_event.clear()
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.progress.start(10)
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
        
        # Redirect logs
        self.log_handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        
        threading.Thread(target=self.run_async_research, daemon=True).start()
        
    def stop_research(self):
        if self.is_running:
            self.stop_event.set()
            logger.warning("Stopping research...")
            
    def run_async_research(self):
        try:
            asyncio.run(self.research_task())
        except Exception as e:
            logger.error(f"Research failed: {e}")
        finally:
            self.cleanup()
            
    async def research_task(self):
        subject = self.subject_var.get()
        
        logger.info(f"Starting research on: {subject}")
        
        if self.stop_event.is_set(): return
        
        # 1. Keywords
        logger.info("Generating keywords...")
        keywords = await generate_keywords(subject, self.general_var.get(), self.academic_var.get())
        logger.info(f"Keywords: {keywords}")
        
        if self.stop_event.is_set(): return

        # 2. Search
        logger.info("Searching sources...")
        snippets = await search_all(keywords)
        logger.info(f"Found {len(snippets)} raw snippets")
        
        if not snippets:
            logger.error("No snippets found.")
            return
            
        if self.stop_event.is_set(): return

        # 3. Filter
        logger.info("Filtering snippets...")
        snippets = await filter_snippets(snippets)
        logger.info(f"Kept {len(snippets)} quality snippets")
        
        if not snippets:
            logger.error("No quality snippets left.")
            return

        if self.stop_event.is_set(): return

        # 4. Bibliometrics
        save_bibliometrics(snippets)
        
        # 5. Synthesis
        logger.info("Synthesizing report...")
        report = await synthesise(snippets, subject)
        
        doc = build_doc(report)
        safe_save(doc, OUTPUT_FILE)
        
        # Also save as markdown
        md_path = OUTPUT_FILE.with_suffix(".md")
        md_path.write_text(report, encoding="utf-8")
        logger.info(f"✅ Saved Markdown report to {md_path}")
        
        logger.info("Research Complete!")
        
    def cleanup(self):
        self.is_running = False
        self.root.after(0, self.reset_ui)
        
    def poll_log_queue(self):
        """Check for new logs in the queue and update UI."""
        try:
            while True:
                record = self.log_queue.get_nowait()
                msg = self.log_handler.format(record) if hasattr(self, 'log_handler') and isinstance(record, logging.LogRecord) else str(record.msg if hasattr(record, 'msg') else record)
                
                self.log_text.config(state='normal')
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)
                self.log_text.config(state='disabled')
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.poll_log_queue)

    def reset_ui(self):
        self.progress.stop()
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        # Remove handler
        if hasattr(self, 'log_handler'):
            import logging
            logging.getLogger().removeHandler(self.log_handler)

def main():
    root = tk.Tk()
    app = ResearchGUI(root)
    root.mainloop()
