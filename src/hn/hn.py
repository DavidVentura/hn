#!/usr/bin/env python3.7
import queue
from pathlib import Path

import gi

from threading import Thread

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk

from pango import html_to_pango
from api import top_stories, get_id
q = queue.Queue()

STYLE_FILE = Path(__file__).parent / 'css' / 'style.css'

class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect("destroy", Gtk.main_quit)
        self.setup_styles()
        self.set_default_size(360, 640)

        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)
        self.stack.set_transition_duration(300)
        self.stack.set_transition_type(Gtk.StackTransitionType.OVER_DOWN_UP)

        self.ct = CommentThread()
        self.news_list = NewsList()

        self.stack.add(self.news_list)
        self.stack.add(self.ct)

        self.add(self.stack)
        self.show_all()
    
    def setup_styles(self):
        css_provider = Gtk.CssProvider()
        context = Gtk.StyleContext()
        screen = Gdk.Screen.get_default()

        css_provider.load_from_path(str(STYLE_FILE))
        context.add_provider_for_screen(screen, css_provider,
                                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def set_thread(self, thread_id):
        self.stack.set_visible_child(self.ct)
        self.ct.set_comments(thread_id)
    
    def set_news(self):
        self.stack.set_visible_child(self.news_list)


class NewsList(Gtk.Grid):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)

        self.add(scrolled_window)
        self.vbox = Gtk.VBox()
        self.vbox.set_homogeneous = False
        scrolled_window.add(self.vbox)
        self.show_all()

    def add_items(self, news_item):
        for child in self.vbox.get_children():
            self.remove(child)

        for i in news_item:
            widget = NewsItem(i)
            self.vbox.pack_start(widget, 0, 0, 0)

class CommentThread(Gtk.Grid):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.get_style_context().add_class('thread-comments')
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_hexpand(True)

        label = Gtk.Label(label='< Go back')
        label.set_hexpand(True)
        label.set_xalign(0)
        label.get_style_context().add_class('thread-back')

        back_event = Gtk.EventBox()
        back_event.add(label)
        back_event.connect('button-release-event', self.back_click)

        self.attach(back_event, 0, 0, 1, 1)
        self.attach(scrolled_window, 0, 1, 1, 10)

        self.vbox = Gtk.VBox()
        self.vbox.set_homogeneous = False
        scrolled_window.add(self.vbox)
        self.show_all()

    def back_click(self, box, event):
        window = self.get_toplevel()
        window.set_news()

    def set_comments(self, thread_id):
        data = get_id(thread_id)
        self._set_comments(data.get('kids', []))

    def _set_comments(self, comments):
        for child in self.vbox.get_children():
            child.destroy()

        for i in comments:
            widget1 = Comment(i)
            self.vbox.pack_start(widget1, 0, 0, 0)  ## fill and expand

class NewsItem(Gtk.Grid):
    def __init__(self, _item_id, *args, **kwds):
        super().__init__(*args, **kwds)
        self.get_style_context().add_class('news-item')

        self.set_column_homogeneous(True)
        self.article_url = None
        self.thread_id = _item_id

        self.title = Gtk.Label()
        self.title.set_line_wrap(True)
        self.title.set_xalign(0)
        self.title.set_hexpand(True)

        self.title_event = Gtk.EventBox()
        self.title_event.connect('button-release-event', self.title_click)
        self.title_event.add(self.title)
        self.attach(self.title_event, 0, 0, 8, 2)

        self.url = Gtk.Label()
        self.url.set_xalign(0)
        self.url.set_hexpand(True)
        self.attach(self.url, 0, 3, 7, 1)

        self.comments = Gtk.Label()
        self.comments.set_hexpand(True)
        self.comments.set_xalign(0)

        self.comments_event = Gtk.EventBox()
        self.comments_event.add(self.comments)
        self.comments_event.connect('button-release-event', self.comments_click)
        self.attach(self.comments_event, 7, 3, 1, 1)

        self.show_all()
        q.put((self._set_content, _item_id))

    def comments_click(self, eventbox, event):
        window = self.get_toplevel()
        window.set_thread(self.thread_id)

    def title_click(self, eventbox, event):
        print("TODO Should go now to ", self.article_url)

    def _set_content(self, _item_id):
        data = get_id(_item_id)
        GLib.idle_add(self.set_content, data, _item_id)

    def set_content(self, data, _item_id):
        comment_count = data.get('descendants', 0)
        kids = data.get('kids', [])
        score = data['score']
        title = data['title']
        if data.get('url'):
            self.article_url = data['url']
            url = data['url'].split('/')[2]
        else:
            url = 'self'
        self.title.set_markup(f'<span size="12000">{title}</span>')
        self.url.set_label(url)
        self.comments.set_label(str(comment_count))


class Comment(Gtk.VBox):
    def __init__(self, _item_id, *args, **kwds):
        super().__init__(*args, **kwds)

        self.comment_body = Gtk.Grid()

        self.comment_body.get_style_context().add_class('comment-item')
        self._time = Gtk.Label()
        self._time.set_margin_bottom(10)
        self._time.set_xalign(0)
        self.comment_body.attach(self._time, 1, 1, 1, 1)

        self.comment = Gtk.Label(label='...')
        self.comment.set_vexpand(True)
        self.comment.set_line_wrap(True)
        self.comment.set_selectable(True)
        self.comment.set_xalign(0)
        self.comment_body.attach(self.comment, 1, 2, 20, 1)

        self.replies_visible = True
        self.replies_container = Gtk.Revealer()
        self.replies_container.set_reveal_child(True)
        self.replies = Gtk.VBox()
        self.replies.get_style_context().add_class('comment-replies')
        self.replies_container.add(self.replies)

        self.add(self.comment_body)
        self.add(self.replies_container)
        self.show_all()

        q.put((self._set_content, _item_id))

    def _set_content(self, _item_id):
        comment = get_id(_item_id)
        GLib.idle_add(self.set_content, comment, _item_id)

    def set_content(self, comment, _item_id):
        if 'text' not in comment:  # deleted
            if 'kids' not in comment:
                self.destroy()
                return
            text = 'deleted'
            by = 'deleted'
        else:
            text = comment['text']
            by = comment['by']
        dead = comment.get('dead', False)

        if dead:
            self.get_style_context().add_class('comment-item-dead')

        self._time.set_markup(f"<small><span foreground='#999'>2m ago</span> - <b>{by}</b></small>")

        text = html_to_pango(text)
        self.comment.set_markup(text)

        kids = comment.get('kids', [])
        if kids:
            self.revealer_event = Gtk.EventBox()
            revealer_label = Gtk.Label(label='Toggle replies')
            revealer_label.get_style_context().add_class('comment-item-toggle')
            self.revealer_event.connect('button-release-event', self.reveal_replies_click)
            self.revealer_event.add(revealer_label)
            self.comment_body.attach(self.revealer_event, 1, 3, 20, 1)
            self.show_all()

        for i in kids:
            wid = Comment(i)
            wid.set_visible(True)
            self.replies.pack_start(wid, 0, 0, 0)

    def reveal_replies_click(self, box, event):
        self.replies_visible = not self.replies_visible
        self.replies_container.set_reveal_child(self.replies_visible)


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="org.example.myapp", **kwargs)

    def do_activate(self):
        self.window = AppWindow(application=self, title="Main Window")
        self.window.present()
        stories = top_stories()
        self.window.news_list.add_items(stories[:50])  # FIXME

def background_fn():
    while True:
        fn, arg = q.get()
        fn(arg)


def main():
    t = Thread(target=background_fn)
    t.daemon = True
    t.start()
    app = Application()
    app.run()

if __name__ == '__main__':
    main()
