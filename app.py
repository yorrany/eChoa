import os, subprocess, threading, urllib.request, json, tempfile
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf

YT_DLP = "/app/bin/yt-dlp"

class EchoaApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="Echoa")
        self.set_border_width(15)
        self.set_default_size(550, -1)
        self.set_resizable(False)
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(vbox)

        # --- CAMPO DE URL COM "X" DENTRO ---
        hbox_input = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.url_entry = Gtk.Entry()
        self.url_entry.set_placeholder_text("Cole o link do vídeo aqui...")
        self.url_entry.set_hexpand(True)
        self.url_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-clear-symbolic")
        self.url_entry.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, False)
        
        self.url_entry.connect("icon-press", self.on_icon_press)
        self.url_entry.connect("changed", self.on_url_changed)
        
        btn_paste = Gtk.Button(label="📋 Colar Link")
        btn_paste.connect("clicked", self.on_paste_clicked)
        
        hbox_input.pack_start(self.url_entry, True, True, 0)
        hbox_input.pack_start(btn_paste, False, False, 0)
        vbox.pack_start(hbox_input, False, False, 0)

        # --- ÁREA DE PREVIEW ---
        self.revealer = Gtk.Revealer()
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        card.set_name("preview-card")
        
        self.img_preview = Gtk.Image()
        self.img_preview.set_size_request(140, 80)
        
        info_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.lbl_title = Gtk.Label(xalign=0)
        self.lbl_title.set_line_wrap(True)
        self.lbl_title.set_max_width_chars(40)
        
        self.lbl_chan = Gtk.Label(xalign=0)
        self.combo_audio = Gtk.ComboBoxText()
        
        info_vbox.pack_start(self.lbl_title, False, False, 0)
        info_vbox.pack_start(self.lbl_chan, False, False, 0)
        info_vbox.pack_start(self.combo_audio, False, False, 4)
        
        card.pack_start(self.img_preview, False, False, 0)
        card.pack_start(info_vbox, True, True, 0)
        self.revealer.add(card)
        vbox.pack_start(self.revealer, False, False, 0)

        # --- SELEÇÃO DE PASTA ---
        hbox_folder = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_folder = Gtk.Label(label="Salvar em:")
        self.folder_btn = Gtk.FileChooserButton(title="Escolha a pasta", action=Gtk.FileChooserAction.SELECT_FOLDER)
        path = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
        if path: self.folder_btn.set_current_folder(path)
        
        hbox_folder.pack_start(lbl_folder, False, False, 0)
        hbox_folder.pack_start(self.folder_btn, True, True, 0)
        vbox.pack_start(hbox_folder, False, False, 0)

        # --- BOTÃO DOWNLOAD ---
        self.btn_dl = Gtk.Button(label="Baixar Áudio Original")
        self.btn_dl.set_sensitive(False)
        self.btn_dl.connect("clicked", self.on_download_clicked)
        vbox.pack_start(self.btn_dl, False, False, 5)

        self.lbl_status = Gtk.Label(label="Aguardando link...")
        vbox.pack_start(self.lbl_status, False, False, 0)

    def on_icon_press(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            entry.set_text("")
            self.revealer.set_reveal_child(False)
            self.btn_dl.set_sensitive(False)
            self.lbl_status.set_text("Aguardando link...")

    def on_paste_clicked(self, btn):
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clip.wait_for_text()
        if text: self.url_entry.set_text(text)

    def on_url_changed(self, widget):
        url = self.url_entry.get_text().strip()
        self.url_entry.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, len(url) > 0)
        if url.startswith("http"):
            self.lbl_status.set_text("Obtendo informações...")
            threading.Thread(target=self.get_meta, args=(url,), daemon=True).start()

    def get_meta(self, url):
        try:
            # Comando com 'extractor-args' para fingir ser o app oficial do YouTube (iOS/Android)
            # Isso é o que há de mais moderno para pular o bloqueio de 'bot'
            cmd = [
                YT_DLP, "-J", "--no-playlist",
                "--extractor-args", "youtube:player-client=ios,web",
                "--no-check-certificates",
                "--geo-bypass",
                url
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            
            if res.returncode == 0:
                data = json.loads(res.stdout)
                GLib.idle_add(self.update_ui, data)
            else:
                # Se falhar, tentamos uma segunda vez com o cliente Android
                cmd_android = [
                    YT_DLP, "-J", "--no-playlist",
                    "--extractor-args", "youtube:player-client=android",
                    url
                ]
                res_alt = subprocess.run(cmd_android, capture_output=True, text=True)
                if res_alt.returncode == 0:
                    data = json.loads(res_alt.stdout)
                    GLib.idle_add(self.update_ui, data)
                else:
                    GLib.idle_add(self.lbl_status.set_text, "Acesso negado pelo YouTube. Tente novamente em instantes.")
        except Exception as e:
            GLib.idle_add(self.lbl_status.set_text, f"Erro de conexão: {str(e)}")


    def update_ui(self, data):
        self.lbl_title.set_markup(f"<b>{data.get('title', 'Vídeo')[:60]}</b>")
        self.lbl_chan.set_text(data.get('uploader', 'Canal'))
        self.combo_audio.remove_all()
        
        formats = data.get('formats', [])
        found = False
        # Adiciona opções de bitrate de áudio
        for f in formats:
            if f.get('vcodec') == 'none' and (f.get('abr') or f.get('tbr')):
                found = True
                q = f.get('abr') or f.get('tbr')
                self.combo_audio.append(f.get('format_id'), f"{int(q)}kbps (.{f.get('ext')})")
        
        if not found: self.combo_audio.append("bestaudio", "Melhor Qualidade")
        
        self.combo_audio.set_active(0)
        self.btn_dl.set_sensitive(True)
        self.revealer.set_reveal_child(True)
        self.lbl_status.set_text("Pronto para baixar.")
        
        thumb_url = data.get('thumbnail')
        if thumb_url: threading.Thread(target=self.load_thumb, args=(thumb_url,), daemon=True).start()

    def load_thumb(self, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as r:
                loader = GdkPixbuf.PixbufLoader()
                loader.write(r.read())
                loader.close()
                pix = loader.get_pixbuf()
                scaled = pix.scale_simple(140, 80, GdkPixbuf.InterpType.BILINEAR)
                GLib.idle_add(self.img_preview.set_from_pixbuf, scaled)
        except: pass

    def on_download_clicked(self, btn):
        url = self.url_entry.get_text()
        fmt = self.combo_audio.get_active_id() or "bestaudio"
        dest = self.folder_btn.get_filename()
        self.btn_dl.set_sensitive(False)
        self.lbl_status.set_text("Baixando...")
        threading.Thread(target=self.run_dl, args=(url, fmt, dest), daemon=True).start()

    def run_dl(self, url, fmt, dest):
        cmd = [YT_DLP, "-f", fmt, "-x", "--audio-format", "mp3", "-o", f"{dest}/%(title)s.%(ext)s", url]
        res = subprocess.run(cmd)
        GLib.idle_add(self.lbl_status.set_text, "Sucesso! Áudio salvo." if res.returncode == 0 else "Falha no download.")
        GLib.idle_add(self.btn_dl.set_sensitive, True)

if __name__ == "__main__":
    win = EchoaApp()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
