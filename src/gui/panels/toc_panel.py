"""
TocPanel — interactive Table of Contents editor panel.

Features
--------
• Treeview showing all TOC entries indented by their level.
• Click to navigate directly to the entry's page.
• Double-click to rename an entry in-place.
• Toolbar buttons: Add Entry, Delete, Move Up, Move Down, Indent, Outdent.
• All edits are dispatched as a ``ModifyTocCommand`` so they participate in
  the application's undo / redo history.
• Refreshes automatically when ``reset(doc)`` is called (e.g. on file open).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from typing import Callable

from src.gui.theme import PALETTE, FONT_LABEL, FONT_UI, FONT_SMALL, PAD_S, PAD_M


# ── helpers ───────────────────────────────────────────────────────────────────

def _mk_btn(parent, text: str, cmd: Callable, tooltip: str = "") -> tk.Button:
    b = tk.Button(
        parent, text=text, command=cmd,
        bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
        activebackground=PALETTE["accent_dim"],
        activeforeground=PALETTE["accent_light"],
        font=("Helvetica Neue", 9), relief="flat", bd=0,
        padx=6, pady=3, cursor="hand2", highlightthickness=0,
    )
    b.pack(side=tk.LEFT, padx=1)
    if tooltip:
        b.bind("<Enter>", lambda e, b=b, t=tooltip: _show_tip(b, t))
        b.bind("<Leave>", lambda e: _hide_tip())
    return b


_tip_window: tk.Toplevel | None = None


def _show_tip(widget: tk.Widget, text: str) -> None:
    global _tip_window
    _hide_tip()
    x = widget.winfo_rootx() + 20
    y = widget.winfo_rooty() + widget.winfo_height() + 2
    _tip_window = tk.Toplevel(widget)
    _tip_window.wm_overrideredirect(True)
    _tip_window.wm_geometry(f"+{x}+{y}")
    tk.Label(
        _tip_window, text=text,
        bg="#FFFFCC", fg="#000000",
        font=("Helvetica Neue", 8), relief="solid", bd=1, padx=4, pady=2,
    ).pack()


def _hide_tip() -> None:
    global _tip_window
    if _tip_window:
        try:
            _tip_window.destroy()
        except Exception:
            pass
        _tip_window = None


# ── TocPanel ──────────────────────────────────────────────────────────────────

class TocPanel:
    """
    Table of Contents panel.

    Parameters
    ----------
    parent : tk.Widget
        Container to pack into (normally a Notebook tab frame).
    on_navigate : callable(page_idx: int)
        Called (0-based index) when the user clicks an entry to jump to it.
    on_toc_changed : callable(new_toc: list[list])
        Called with the updated ``[level, title, page]`` list whenever the
        user makes an edit.  The caller is responsible for wrapping this in a
        ``ModifyTocCommand`` and pushing it to history.
    get_page_count : callable → int
        Returns the current document's page count (used when adding entries).
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_navigate: Callable[[int], None],
        on_toc_changed: Callable[[list], None],
        get_page_count: Callable[[], int],
    ) -> None:
        self._on_navigate    = on_navigate
        self._on_toc_changed = on_toc_changed
        self._get_page_count = get_page_count

        # Internal state
        self._toc: list[list] = []   # current [level, title, page] list
        self._loading = False         # suppress change events while populating

        self.frame = tk.Frame(parent, bg=PALETTE["bg_panel"])
        self.frame.pack(fill=tk.BOTH, expand=True)

        self._build()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── empty state label (shown when TOC is empty) ───────────────────────
        self._empty_frame = tk.Frame(self.frame, bg=PALETTE["bg_panel"])
        self._empty_frame.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(
            self._empty_frame,
            text="No bookmarks",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
            font=("Helvetica Neue", 10, "bold"),
        ).pack()
        tk.Label(
            self._empty_frame,
            text="Click + to add the first entry.",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
            font=FONT_SMALL,
        ).pack(pady=(2, 0))

        # ── Treeview ──────────────────────────────────────────────────────────
        tree_frame = tk.Frame(self.frame, bg=PALETTE["bg_panel"])
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        style = ttk.Style()
        style.configure(
            "Toc.Treeview",
            background=PALETTE["bg_panel"],
            foreground=PALETTE["fg_primary"],
            fieldbackground=PALETTE["bg_panel"],
            borderwidth=0,
            rowheight=22,
            font=("Helvetica Neue", 9),
        )
        style.configure(
            "Toc.Treeview.Heading",
            background=PALETTE["bg_mid"],
            foreground=PALETTE["fg_dim"],
            relief="flat",
            font=("Helvetica Neue", 8, "bold"),
        )
        style.map(
            "Toc.Treeview",
            background=[("selected", PALETTE["accent_dim"])],
            foreground=[("selected", PALETTE["accent_light"])],
        )

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree = ttk.Treeview(
            tree_frame,
            style="Toc.Treeview",
            columns=("page",),
            show="tree headings",
            yscrollcommand=vsb.set,
            selectmode="browse",
        )
        vsb.config(command=self._tree.yview)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._tree.heading("#0",    text="Title", anchor="w")
        self._tree.heading("page",  text="Page",  anchor="e")
        self._tree.column("#0",    minwidth=80,  stretch=True)
        self._tree.column("page",  width=44, minwidth=36, stretch=False, anchor="e")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>",         self._on_double_click)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = tk.Frame(self.frame, bg=PALETTE["bg_mid"], height=30)
        toolbar.pack(fill=tk.X, side=tk.BOTTOM)
        toolbar.pack_propagate(False)

        _mk_btn(toolbar, "+ Add",     self._add_entry,   "Add new bookmark (below selection)")
        _mk_btn(toolbar, "✕",         self._delete_entry, "Delete selected bookmark")

        # Separator
        tk.Frame(toolbar, bg=PALETTE["border"], width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=6, padx=2)

        _mk_btn(toolbar, "↑",         self._move_up,     "Move entry up")
        _mk_btn(toolbar, "↓",         self._move_down,   "Move entry down")

        # Separator
        tk.Frame(toolbar, bg=PALETTE["border"], width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=6, padx=2)

        _mk_btn(toolbar, "← Out",     self._outdent,     "Decrease indent level")
        _mk_btn(toolbar, "In →",      self._indent,      "Increase indent level")

    # ── public API ────────────────────────────────────────────────────────────

    def reset(self, toc: list[list]) -> None:
        """
        Repopulate the tree with *toc*.

        *toc* is the standard PyMuPDF ``[[level, title, page], …]`` list.
        Call with an empty list to show the "No bookmarks" placeholder.
        """
        self._toc = [list(e) for e in toc]
        self._populate_tree()

    def get_toc(self) -> list[list]:
        """Return a copy of the current TOC list (reconstructed from tree)."""
        return [list(e) for e in self._toc]

    # ── tree ↔ data sync ──────────────────────────────────────────────────────

    def _populate_tree(self) -> None:
        """Rebuild the Treeview from ``self._toc``."""
        self._loading = True
        self._tree.delete(*self._tree.get_children())

        if not self._toc:
            self._empty_frame.place(relx=0.5, rely=0.45, anchor="center")
            self._loading = False
            return

        self._empty_frame.place_forget()

        # Stack of (level, tree_item_id) used to determine the correct parent.
        stack: list[tuple[int, str]] = []

        for idx, entry in enumerate(self._toc):
            level, title, page = entry[0], entry[1], entry[2]
            # Pop stack until we find a parent whose level < this entry's level
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else ""
            iid = self._tree.insert(
                parent, "end",
                iid=str(idx),
                text=f"  {title}",
                values=(page,),
                open=True,
            )
            stack.append((level, iid))

        self._loading = False

    def _tree_to_list(self) -> list[list]:
        """
        Walk the Treeview items depth-first and reconstruct the flat TOC list.

        Level is derived from the nesting depth in the tree (root children = 1).
        """
        result: list[list] = []

        def _walk(item_id: str, depth: int) -> None:
            if item_id:  # skip the invisible root ""
                text  = self._tree.item(item_id, "text").strip()
                # Ensure page is cast safely back to an integer
                page  = int(self._tree.set(item_id, "page"))
                result.append([depth, text, page])
            
            # Fix: The root element ("") must pass depth 1 to its children.
            # Normal elements pass their current depth + 1.
            next_depth = depth + 1 if item_id else 1
            
            for child in self._tree.get_children(item_id):
                _walk(child, next_depth)

        _walk("", 0)
        return result

    def _commit(self) -> None:
        """Sync _toc from the tree, then fire the change callback."""
        self._toc = self._tree_to_list()
        if not self._loading:
            self._on_toc_changed(self.get_toc())

    # ── Treeview event handlers ───────────────────────────────────────────────

    def _on_select(self, _event: tk.Event) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        iid  = sel[0]
        try:
            page_val = self._tree.set(iid, "page")
            if page_val:
                page = int(page_val)
                self._on_navigate(page - 1)   # convert 1-based → 0-based
        except ValueError:
            pass

    def _on_double_click(self, event: tk.Event) -> None:
        """Inline rename on double-click."""
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        col = self._tree.identify_column(event.x)
        if col == "#1":   # page column
            self._edit_page(iid)
        else:
            self._edit_title(iid)

    # ── inline editing ────────────────────────────────────────────────────────

    def _edit_title(self, iid: str) -> None:
        bbox = self._tree.bbox(iid, "#0")
        if not bbox:
            return
        x, y, w, h = bbox
        old_title = self._tree.item(iid, "text").strip()

        entry_var = tk.StringVar(value=old_title)
        entry = tk.Entry(
            self._tree, textvariable=entry_var,
            bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
            insertbackground=PALETTE["fg_primary"],
            relief="flat", highlightthickness=1,
            highlightbackground=PALETTE["accent"],
            font=("Helvetica Neue", 9),
        )
        entry.place(x=x + 2, y=y + 1, width=w - 4, height=h - 2)
        entry.focus_set()
        entry.select_range(0, tk.END)

        def _confirm(e=None):
            new_title = entry_var.get().strip()
            entry.destroy()
            if new_title and new_title != old_title:
                self._tree.item(iid, text=f"  {new_title}")
                self._commit()

        def _cancel(e=None):
            entry.destroy()

        entry.bind("<Return>",  _confirm)
        entry.bind("<Escape>",  _cancel)
        entry.bind("<FocusOut>", _confirm)

    def _edit_page(self, iid: str) -> None:
        bbox = self._tree.bbox(iid, "page")
        if not bbox:
            return
        x, y, w, h = bbox
        old_page = self._tree.set(iid, "page")
        entry_var = tk.StringVar(value=old_page)
        entry = tk.Entry(
            self._tree, textvariable=entry_var,
            bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
            insertbackground=PALETTE["fg_primary"],
            relief="flat", highlightthickness=1,
            highlightbackground=PALETTE["accent"],
            font=("Helvetica Neue", 9), justify="right",
        )
        entry.place(x=x + 1, y=y + 1, width=w - 2, height=h - 2)
        entry.focus_set()
        entry.select_range(0, tk.END)

        def _confirm(e=None):
            raw = entry_var.get().strip()
            entry.destroy()
            try:
                page_num = int(raw)
                max_page = self._get_page_count()
                if 1 <= page_num <= max_page:
                    self._tree.set(iid, "page", str(page_num))
                    self._commit()
                else:
                    messagebox.showwarning(
                        "Invalid Page",
                        f"Page must be between 1 and {max_page}.",
                    )
            except ValueError:
                pass

        def _cancel(e=None):
            entry.destroy()

        entry.bind("<Return>",  _confirm)
        entry.bind("<Escape>",  _cancel)
        entry.bind("<FocusOut>", _confirm)

    # ── toolbar actions ───────────────────────────────────────────────────────

    def _selected_iid(self) -> str | None:
        sel = self._tree.selection()
        return sel[0] if sel else None

    def _add_entry(self) -> None:
        """Add a new entry below the current selection (or at the end)."""
        max_page = self._get_page_count()
        if max_page == 0:
            return

        # FIX: Added parent=self.frame to strictly bind the dialog to the UI
        title = simpledialog.askstring(
            "Add Bookmark", "Bookmark title:",
            initialvalue="New Bookmark",
            parent=self.frame
        )
        if not title:
            return
        title = title.strip()

        # FIX: Added parent=self.frame
        page_str = simpledialog.askstring(
            "Add Bookmark", f"Page number (1 – {max_page}):",
            initialvalue="1",
            parent=self.frame
        )
        if not page_str:
            return
        try:
            page = int(page_str.strip())
            if not (1 <= page <= max_page):
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid Page",
                                   f"Page must be between 1 and {max_page}.",
                                   parent=self.frame)
            return

        sel = self._selected_iid()

        # Determine parent and insert position
        if sel:
            parent = self._tree.parent(sel)
            idx    = self._tree.index(sel) + 1
        else:
            parent = ""
            idx    = "end"

        level = self._depth_of(parent) + 1 if parent else 1
        iid   = self._tree.insert(
            parent, idx,
            text=f"  {title}",
            values=(page,),
            open=True,
        )
        self._tree.selection_set(iid)
        self._tree.see(iid)
        self._empty_frame.place_forget()
        self._commit()

    def _delete_entry(self) -> None:
        sel = self._selected_iid()
        if not sel:
            return
        title = self._tree.item(sel, "text").strip()
        children = self._tree.get_children(sel)
        extra = f"\n\nThis will also remove {len(children)} child bookmark(s)." if children else ""
        if not messagebox.askyesno(
            "Delete Bookmark", f'Delete "{title}"?{extra}', icon="warning"
        ):
            return
        # Select next sibling / parent before deleting
        next_sel = (self._tree.next(sel)
                    or self._tree.prev(sel)
                    or self._tree.parent(sel))
        self._tree.delete(sel)
        if next_sel:
            self._tree.selection_set(next_sel)
        if not self._tree.get_children():
            self._empty_frame.place(relx=0.5, rely=0.45, anchor="center")
        self._commit()

    def _move_up(self) -> None:
        sel = self._selected_iid()
        if not sel:
            return
        prev = self._tree.prev(sel)
        if not prev:
            return
        parent = self._tree.parent(sel)
        idx    = self._tree.index(prev)
        self._tree.move(sel, parent, idx)
        self._commit()

    def _move_down(self) -> None:
        sel = self._selected_iid()
        if not sel:
            return
        nxt = self._tree.next(sel)
        if not nxt:
            return
        parent = self._tree.parent(sel)
        idx    = self._tree.index(nxt)
        self._tree.move(sel, parent, idx)
        self._commit()

    def _indent(self) -> None:
        """Make the selected entry a child of its previous sibling."""
        sel = self._selected_iid()
        if not sel:
            return
        prev = self._tree.prev(sel)
        if not prev:
            return   # no previous sibling to nest under
        self._tree.move(sel, prev, "end")
        self._tree.item(prev, open=True)
        self._commit()

    def _outdent(self) -> None:
        """Move the selected entry up one level (make it a sibling of its parent)."""
        sel = self._selected_iid()
        if not sel:
            return
        parent = self._tree.parent(sel)
        if not parent:
            return   # already at root level
        grandparent = self._tree.parent(parent)
        idx          = self._tree.index(parent) + 1
        self._tree.move(sel, grandparent, idx)
        self._commit()

    # ── depth helper ──────────────────────────────────────────────────────────

    def _depth_of(self, iid: str) -> int:
        """Return the nesting depth (0 = root child) of a tree item."""
        depth = 0
        current = iid
        while True:
            parent = self._tree.parent(current)
            if not parent:
                break
            depth  += 1
            current = parent
        return depth