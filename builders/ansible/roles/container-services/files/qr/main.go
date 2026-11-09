// qr: short links that redirect, and the QR codes that point at them.
//
// A printed QR code encodes https://<public host>/<slug>, never the
// destination, so the destination can change after the code is on paper.
//
// Two listeners, because they face different people:
//
//	public (PUBLIC_ADDR)  GET /<slug> answers 302; GET /healthz. Nothing else
//	                      exists on it, so exposing it exposes no UI or API.
//	admin  (ADMIN_ADDR)   the page and its JSON API. No login of its own: the
//	                      lab's passkey sits in front of it.
package main

import (
	"context"
	"crypto/rand"
	"database/sql"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"regexp"
	"strconv"
	"strings"
	"syscall"
	"time"

	qrcode "github.com/skip2/go-qrcode"
	_ "modernc.org/sqlite"
)

//go:embed index.html
var assets embed.FS

var (
	slugRE   = regexp.MustCompile(`^[a-z0-9][a-z0-9_-]{0,63}$`)
	reserved = map[string]bool{"healthz": true, "api": true, "qr": true, "robots.txt": true, "favicon.ico": true}
)

// Unambiguous when read aloud or typed from a printed sheet: no 0/o, 1/l/i.
const slugAlphabet = "abcdefghjkmnpqrstuvwxyz23456789"

type Link struct {
	Slug      string `json:"slug"`
	Label     string `json:"label"`
	Target    string `json:"target"`
	Short     string `json:"short"`
	Scans     int64  `json:"scans"`
	CreatedAt int64  `json:"created_at"`
	LastScan  *int64 `json:"last_scan"`
}

type app struct {
	db      *sql.DB
	baseURL string // https://go.example, no trailing slash
	host    string // its host, to refuse a destination that points back here
}

func main() {
	base := strings.TrimRight(os.Getenv("PUBLIC_BASE_URL"), "/")
	u, err := url.Parse(base)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
		log.Fatalf("PUBLIC_BASE_URL must be an http(s) URL, got %q", base)
	}
	db, err := openDB(env("DB_PATH", "/data/qr.db"))
	if err != nil {
		log.Fatal(err)
	}
	a := &app{db: db, baseURL: base, host: u.Host}

	// MODE picks which listeners this process runs. In the lab the two run as
	// separate containers over one database, so the one a tunnel can reach has
	// no admin page in it at all. "all" is for running it by hand.
	mode := env("MODE", "all")
	var servers []*http.Server
	switch mode {
	case "all", "public", "admin":
	default:
		log.Fatalf("MODE must be all, public or admin, got %q", mode)
	}
	if mode != "admin" {
		servers = append(servers, &http.Server{Addr: env("PUBLIC_ADDR", ":8080"), Handler: a.publicHandler(),
			ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 60 * time.Second})
	}
	if mode != "public" {
		servers = append(servers, &http.Server{Addr: env("ADMIN_ADDR", ":8081"), Handler: a.adminHandler(),
			ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 15 * time.Second, WriteTimeout: 30 * time.Second, IdleTimeout: 60 * time.Second})
	}

	for _, s := range servers {
		go func(s *http.Server) {
			log.Printf("listening on %s (mode %s)", s.Addr, mode)
			if err := s.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
				log.Fatal(err)
			}
		}(s)
	}

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	for _, s := range servers {
		s.Shutdown(ctx)
	}
	db.Close()
}

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func openDB(path string) (*sql.DB, error) {
	db, err := sql.Open("sqlite", "file:"+path+"?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)&_pragma=synchronous(NORMAL)")
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1) // one writer; a handful of scans a day does not need more
	_, err = db.Exec(`CREATE TABLE IF NOT EXISTS links (
		slug       TEXT PRIMARY KEY,
		target     TEXT NOT NULL,
		label      TEXT NOT NULL DEFAULT '',
		scans      INTEGER NOT NULL DEFAULT 0,
		created_at INTEGER NOT NULL,
		last_scan  INTEGER
	)`)
	return db, err
}

// ---------------------------------------------------------------- public ---

func (a *app) publicHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			http.Error(w, "not found", http.StatusNotFound)
			return
		}
		w.Header().Set("X-Robots-Tag", "noindex")
		switch p := strings.TrimPrefix(r.URL.Path, "/"); p {
		case "healthz":
			if err := a.db.PingContext(r.Context()); err != nil {
				http.Error(w, "db", http.StatusServiceUnavailable)
				return
			}
			fmt.Fprintln(w, "ok")
		case "robots.txt":
			fmt.Fprint(w, "User-agent: *\nDisallow: /\n")
		default:
			a.redirect(w, r, strings.ToLower(p))
		}
	})
}

func (a *app) redirect(w http.ResponseWriter, r *http.Request, slug string) {
	if !slugRE.MatchString(slug) {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	var target string
	var err error
	if r.Method == http.MethodHead {
		// Link-preview bots and uptime probes use HEAD; they are not scans.
		err = a.db.QueryRowContext(r.Context(), `SELECT target FROM links WHERE slug = ?`, slug).Scan(&target)
	} else {
		err = a.db.QueryRowContext(r.Context(),
			`UPDATE links SET scans = scans + 1, last_scan = ? WHERE slug = ? RETURNING target`,
			time.Now().Unix(), slug).Scan(&target)
	}
	if errors.Is(err, sql.ErrNoRows) {
		http.Error(w, "not found", http.StatusNotFound)
		return
	} else if err != nil {
		log.Printf("redirect %s: %v", slug, err)
		http.Error(w, "unavailable", http.StatusServiceUnavailable)
		return
	}
	// 302 and no-store: the destination is meant to change, so nothing
	// between the phone and here may remember the old one.
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Referrer-Policy", "no-referrer")
	http.Redirect(w, r, target, http.StatusFound)
}

// ----------------------------------------------------------------- admin ---

func (a *app) adminHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, r *http.Request) {
		b, _ := assets.ReadFile("index.html")
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Content-Security-Policy", "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
		w.Write(b)
	})
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintln(w, "ok") })
	mux.HandleFunc("GET /api/links", a.listLinks)
	mux.HandleFunc("POST /api/links", a.createLink)
	mux.HandleFunc("PATCH /api/links/{slug}", a.updateLink)
	mux.HandleFunc("DELETE /api/links/{slug}", a.deleteLink)
	mux.HandleFunc("GET /qr/{file}", a.qrImage)
	return sameOrigin(mux)
}

// sameOrigin refuses a browser request that another site caused. The page and
// its API share one origin, so a write that carries a different Origin is not
// from the page. Requests with no Origin (curl, the page's own GETs) pass.
func sameOrigin(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			if o := r.Header.Get("Origin"); o != "" {
				if u, err := url.Parse(o); err != nil || u.Host != r.Host {
					http.Error(w, "cross-origin write refused", http.StatusForbidden)
					return
				}
			}
		}
		next.ServeHTTP(w, r)
	})
}

type linkInput struct {
	Slug   *string `json:"slug"`
	Target *string `json:"target"`
	Label  *string `json:"label"`
}

func (a *app) listLinks(w http.ResponseWriter, r *http.Request) {
	rows, err := a.db.QueryContext(r.Context(),
		`SELECT slug, label, target, scans, created_at, last_scan FROM links ORDER BY created_at DESC, slug`)
	if err != nil {
		fail(w, err)
		return
	}
	defer rows.Close()
	out := []Link{}
	for rows.Next() {
		var l Link
		if err := rows.Scan(&l.Slug, &l.Label, &l.Target, &l.Scans, &l.CreatedAt, &l.LastScan); err != nil {
			fail(w, err)
			return
		}
		l.Short = a.baseURL + "/" + l.Slug
		out = append(out, l)
	}
	writeJSON(w, http.StatusOK, out)
}

func (a *app) createLink(w http.ResponseWriter, r *http.Request) {
	in, ok := decode(w, r)
	if !ok {
		return
	}
	target, err := a.cleanTarget(deref(in.Target))
	if err != nil {
		bad(w, err.Error())
		return
	}
	label := strings.TrimSpace(deref(in.Label))
	if len(label) > 120 {
		bad(w, "label is longer than 120 characters")
		return
	}
	slug := strings.ToLower(strings.TrimSpace(deref(in.Slug)))
	custom := slug != ""
	if custom {
		if !slugRE.MatchString(slug) || reserved[slug] {
			bad(w, "short name: 1-64 characters of a-z, 0-9, - and _, starting with a letter or digit, and not a reserved word")
			return
		}
	}
	for attempt := 0; attempt < 8; attempt++ {
		if !custom {
			slug = randomSlug(6)
		}
		_, err = a.db.ExecContext(r.Context(),
			`INSERT INTO links (slug, target, label, created_at) VALUES (?, ?, ?, ?)`,
			slug, target, label, time.Now().Unix())
		if err == nil {
			a.respondLink(w, r, http.StatusCreated, slug)
			return
		}
		if strings.Contains(err.Error(), "UNIQUE") {
			if custom {
				writeJSON(w, http.StatusConflict, map[string]string{"error": "that short name is taken"})
				return
			}
			continue // a random one collided; draw again
		}
		fail(w, err)
		return
	}
	fail(w, errors.New("could not find a free short name"))
}

func (a *app) updateLink(w http.ResponseWriter, r *http.Request) {
	slug := r.PathValue("slug")
	in, ok := decode(w, r)
	if !ok {
		return
	}
	if in.Target != nil {
		t, err := a.cleanTarget(*in.Target)
		if err != nil {
			bad(w, err.Error())
			return
		}
		in.Target = &t
	}
	if in.Label != nil {
		l := strings.TrimSpace(*in.Label)
		if len(l) > 120 {
			bad(w, "label is longer than 120 characters")
			return
		}
		in.Label = &l
	}
	res, err := a.db.ExecContext(r.Context(),
		`UPDATE links SET target = COALESCE(?, target), label = COALESCE(?, label) WHERE slug = ?`,
		in.Target, in.Label, slug)
	if err != nil {
		fail(w, err)
		return
	}
	if n, _ := res.RowsAffected(); n == 0 {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "no such link"})
		return
	}
	a.respondLink(w, r, http.StatusOK, slug)
}

func (a *app) deleteLink(w http.ResponseWriter, r *http.Request) {
	res, err := a.db.ExecContext(r.Context(), `DELETE FROM links WHERE slug = ?`, r.PathValue("slug"))
	if err != nil {
		fail(w, err)
		return
	}
	if n, _ := res.RowsAffected(); n == 0 {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "no such link"})
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (a *app) respondLink(w http.ResponseWriter, r *http.Request, code int, slug string) {
	l := Link{Slug: slug, Short: a.baseURL + "/" + slug}
	err := a.db.QueryRowContext(r.Context(),
		`SELECT label, target, scans, created_at, last_scan FROM links WHERE slug = ?`, slug).
		Scan(&l.Label, &l.Target, &l.Scans, &l.CreatedAt, &l.LastScan)
	if err != nil {
		fail(w, err)
		return
	}
	writeJSON(w, code, l)
}

// qrImage serves /qr/<slug>.png?size=N and /qr/<slug>.svg. The code encodes the
// short address only; it never needs redrawing when the destination changes.
func (a *app) qrImage(w http.ResponseWriter, r *http.Request) {
	file := r.PathValue("file")
	dot := strings.LastIndexByte(file, '.')
	if dot < 0 {
		http.NotFound(w, r)
		return
	}
	slug, ext := file[:dot], file[dot+1:]
	var one int
	if err := a.db.QueryRowContext(r.Context(), `SELECT 1 FROM links WHERE slug = ?`, slug).Scan(&one); err != nil {
		http.NotFound(w, r)
		return
	}
	// High (25% recoverable) rather than Medium: a printed code gets scuffed,
	// folded and photographed at an angle.
	q, err := qrcode.New(a.baseURL+"/"+slug, qrcode.High)
	if err != nil {
		fail(w, err)
		return
	}
	w.Header().Set("Cache-Control", "no-cache")
	switch ext {
	case "png":
		size := 512
		if s, err := strconv.Atoi(r.URL.Query().Get("size")); err == nil {
			size = max(128, min(s, 2048))
		}
		png, err := q.PNG(size)
		if err != nil {
			fail(w, err)
			return
		}
		w.Header().Set("Content-Type", "image/png")
		if r.URL.Query().Has("download") {
			w.Header().Set("Content-Disposition", `attachment; filename="`+slug+`.png"`)
		}
		w.Write(png)
	case "svg":
		w.Header().Set("Content-Type", "image/svg+xml")
		if r.URL.Query().Has("download") {
			w.Header().Set("Content-Disposition", `attachment; filename="`+slug+`.svg"`)
		}
		w.Write(svg(q.Bitmap()))
	default:
		http.NotFound(w, r)
	}
}

// svg draws the modules as runs of one path, so a print shop gets a vector
// that stays sharp at any size.
func svg(bm [][]bool) []byte {
	n := len(bm)
	var b strings.Builder
	fmt.Fprintf(&b, `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" shape-rendering="crispEdges"><rect width="%d" height="%d" fill="#fff"/><path fill="#000" d="`, n, n, n, n)
	for y, row := range bm {
		for x := 0; x < n; {
			if !row[x] {
				x++
				continue
			}
			start := x
			for x < n && row[x] {
				x++
			}
			fmt.Fprintf(&b, "M%d %dh%dv1h-%dz", start, y, x-start, x-start)
		}
	}
	b.WriteString(`"/></svg>`)
	return []byte(b.String())
}

// ---------------------------------------------------------------- helpers ---

// cleanTarget accepts only a web address that is not this service itself.
// javascript:, data: and file: would turn a scan into something other than a
// page load; the public host would turn it into a loop.
func (a *app) cleanTarget(raw string) (string, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "", errors.New("destination is required")
	}
	if len(raw) > 2048 {
		return "", errors.New("destination is longer than 2048 characters")
	}
	u, err := url.Parse(raw)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
		return "", errors.New("destination must be a full http:// or https:// address")
	}
	if strings.EqualFold(u.Host, a.host) {
		return "", errors.New("destination points back at this service")
	}
	return u.String(), nil
}

func randomSlug(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	for i := range b {
		b[i] = slugAlphabet[int(b[i])%len(slugAlphabet)]
	}
	return string(b)
}

func decode(w http.ResponseWriter, r *http.Request) (linkInput, bool) {
	var in linkInput
	r.Body = http.MaxBytesReader(w, r.Body, 16<<10)
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(&in); err != nil {
		bad(w, "invalid JSON body")
		return in, false
	}
	return in, true
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}

func bad(w http.ResponseWriter, msg string) {
	writeJSON(w, http.StatusBadRequest, map[string]string{"error": msg})
}

func fail(w http.ResponseWriter, err error) {
	log.Printf("error: %v", err)
	writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "internal error"})
}
