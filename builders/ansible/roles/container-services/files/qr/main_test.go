package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
)

func newApp(t *testing.T) *app {
	t.Helper()
	db, err := openDB(filepath.Join(t.TempDir(), "qr.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	return &app{db: db, baseURL: "https://go.example.test", host: "go.example.test"}
}

func do(h http.Handler, method, path, body string, hdr ...string) *httptest.ResponseRecorder {
	r := httptest.NewRequest(method, path, strings.NewReader(body))
	for i := 0; i+1 < len(hdr); i += 2 {
		r.Header.Set(hdr[i], hdr[i+1])
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	return w
}

func create(t *testing.T, a *app, body string) Link {
	t.Helper()
	w := do(a.adminHandler(), "POST", "/api/links", body)
	if w.Code != http.StatusCreated {
		t.Fatalf("create %s: %d %s", body, w.Code, w.Body)
	}
	var l Link
	json.Unmarshal(w.Body.Bytes(), &l)
	return l
}

func TestScanRedirectsAndCounts(t *testing.T) {
	a := newApp(t)
	l := create(t, a, `{"slug":"Form","target":"https://forms.gle/abc"}`)
	if l.Slug != "form" {
		t.Fatalf("slug not lowercased: %q", l.Slug)
	}
	for i := 0; i < 2; i++ {
		w := do(a.publicHandler(), "GET", "/FORM", "")
		if w.Code != http.StatusFound || w.Header().Get("Location") != "https://forms.gle/abc" {
			t.Fatalf("scan %d: %d %q", i, w.Code, w.Header().Get("Location"))
		}
		if w.Header().Get("Cache-Control") != "no-store" {
			t.Fatal("redirect must not be cacheable")
		}
	}
	do(a.publicHandler(), "HEAD", "/form", "") // a preview bot, not a scan
	var links []Link
	json.Unmarshal(do(a.adminHandler(), "GET", "/api/links", "").Body.Bytes(), &links)
	if links[0].Scans != 2 || links[0].LastScan == nil {
		t.Fatalf("want 2 scans, got %+v", links[0])
	}
}

func TestDestinationChangesWithoutNewCode(t *testing.T) {
	a := newApp(t)
	create(t, a, `{"slug":"form","target":"https://old.example/a"}`)
	w := do(a.adminHandler(), "PATCH", "/api/links/form", `{"target":"https://new.example/b"}`)
	if w.Code != 200 {
		t.Fatal(w.Code, w.Body)
	}
	if loc := do(a.publicHandler(), "GET", "/form", "").Header().Get("Location"); loc != "https://new.example/b" {
		t.Fatalf("still redirecting to %q", loc)
	}
}

func TestPublicSideExposesNothingElse(t *testing.T) {
	a := newApp(t)
	create(t, a, `{"slug":"form","target":"https://x.example"}`)
	for _, p := range []string{"/", "/api/links", "/qr/form.png", "/index.html", "/form/extra", "/..%2fetc"} {
		if w := do(a.publicHandler(), "GET", p, ""); w.Code != 404 {
			t.Errorf("public %s -> %d, want 404", p, w.Code)
		}
	}
	for _, m := range []string{"POST", "DELETE", "PATCH"} {
		if w := do(a.publicHandler(), m, "/form", `{}`); w.Code != 404 {
			t.Errorf("public %s -> %d, want 404", m, w.Code)
		}
	}
	if w := do(a.publicHandler(), "GET", "/healthz", ""); w.Code != 200 {
		t.Errorf("healthz -> %d", w.Code)
	}
}

func TestRejectsBadDestinations(t *testing.T) {
	a := newApp(t)
	for _, target := range []string{
		"javascript:alert(1)", "data:text/html,hi", "file:///etc/passwd", "ftp://x.example",
		"//x.example", "forms.gle/abc", "", "https://go.example.test/loop", "https://GO.example.test/loop",
		"https://x.example/" + strings.Repeat("a", 2100),
	} {
		b, _ := json.Marshal(map[string]string{"target": target})
		if w := do(a.adminHandler(), "POST", "/api/links", string(b)); w.Code != 400 {
			t.Errorf("target %.40q -> %d, want 400", target, w.Code)
		}
	}
}

func TestSlugRules(t *testing.T) {
	a := newApp(t)
	for _, slug := range []string{"api", "healthz", "qr", "has space", "-lead", "a/b", "ünï", strings.Repeat("a", 65)} {
		b, _ := json.Marshal(map[string]string{"slug": slug, "target": "https://x.example"})
		if w := do(a.adminHandler(), "POST", "/api/links", string(b)); w.Code != 400 {
			t.Errorf("slug %q -> %d, want 400", slug, w.Code)
		}
	}
	create(t, a, `{"slug":"taken","target":"https://x.example"}`)
	if w := do(a.adminHandler(), "POST", "/api/links", `{"slug":"taken","target":"https://y.example"}`); w.Code != 409 {
		t.Errorf("duplicate -> %d, want 409", w.Code)
	}
	l := create(t, a, `{"target":"https://x.example"}`)
	if len(l.Slug) != 6 || strings.ContainsAny(l.Slug, "0oil1") {
		t.Errorf("random slug %q", l.Slug)
	}
}

func TestCrossOriginWriteRefused(t *testing.T) {
	a := newApp(t)
	h := a.adminHandler()
	body := `{"slug":"evil","target":"https://x.example"}`
	if w := do(h, "POST", "/api/links", body, "Origin", "https://evil.example"); w.Code != 403 {
		t.Errorf("cross-origin POST -> %d, want 403", w.Code)
	}
	if w := do(h, "POST", "/api/links", body, "Origin", "http://example.com"); w.Code != 201 {
		// httptest requests carry Host example.com
		t.Errorf("same-origin POST -> %d, want 201", w.Code)
	}
	create(t, a, `{"slug":"keep","target":"https://x.example"}`)
	if w := do(h, "DELETE", "/api/links/keep", "", "Origin", "https://evil.example"); w.Code != 403 {
		t.Errorf("cross-origin DELETE -> %d, want 403", w.Code)
	}
}

func TestDelete(t *testing.T) {
	a := newApp(t)
	create(t, a, `{"slug":"gone","target":"https://x.example"}`)
	if w := do(a.adminHandler(), "DELETE", "/api/links/gone", ""); w.Code != 204 {
		t.Fatal(w.Code)
	}
	if w := do(a.publicHandler(), "GET", "/gone", ""); w.Code != 404 {
		t.Fatalf("deleted link still answers %d", w.Code)
	}
	if w := do(a.adminHandler(), "DELETE", "/api/links/gone", ""); w.Code != 404 {
		t.Fatalf("second delete -> %d", w.Code)
	}
}

func TestQRImages(t *testing.T) {
	a := newApp(t)
	create(t, a, `{"slug":"form","target":"https://x.example"}`)
	h := a.adminHandler()
	w := do(h, "GET", "/qr/form.png?size=300", "")
	if w.Code != 200 || w.Header().Get("Content-Type") != "image/png" || !strings.HasPrefix(w.Body.String(), "\x89PNG") {
		t.Fatalf("png: %d %q", w.Code, w.Header().Get("Content-Type"))
	}
	w = do(h, "GET", "/qr/form.svg", "")
	if w.Code != 200 || !strings.HasPrefix(w.Body.String(), "<svg") {
		t.Fatalf("svg: %d", w.Code)
	}
	for _, p := range []string{"/qr/nope.png", "/qr/form.gif", "/qr/form"} {
		if w := do(h, "GET", p, ""); w.Code != 404 {
			t.Errorf("%s -> %d, want 404", p, w.Code)
		}
	}
}
