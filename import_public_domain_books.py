#!/usr/bin/env python3
"""Download complete public-domain texts from Project Gutenberg and import them into the reader.

This script replaces only the three library books/chapters. User accounts, lesson progress,
assignment scores, and course data remain intact. Existing reading progress for replaced
chapters is cleared because chapter IDs change.
"""
from __future__ import annotations
import os, re, sqlite3, sys, urllib.request
from textwrap import shorten

from app import DB
from reader_migrations import ensure_reader_schema

BOOKS = [
    {
        'id': 1,
        'title': 'The Categories',
        'author': 'Aristotle',
        'url': 'https://www.gutenberg.org/cache/epub/2412/pg2412.txt',
        'reading_level': 'Approx. grades 8–9',
        'description': 'A classical foundation for categories, predication, definition, and disciplined reasoning.',
        'split': 'aristotle',
    },
    {
        'id': 2,
        'title': 'A Treatise Concerning the Principles of Human Knowledge',
        'author': 'George Berkeley',
        'url': 'https://www.gutenberg.org/cache/epub/4723/pg4723.txt',
        'reading_level': 'Approx. grades 10–12',
        'description': 'Primary-source reading on ideas, perception, matter, and what it means for something to exist.',
        'split': 'berkeley',
    },
    {
        'id': 3,
        'title': 'An Enquiry Concerning Human Understanding',
        'author': 'David Hume',
        'url': 'https://www.gutenberg.org/cache/epub/9662/pg9662.txt',
        'reading_level': 'College-level; tutor support recommended',
        'description': 'Primary-source reading on causation, evidence, probability, induction, and skepticism.',
        'split': 'hume',
    },
]


def download(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent':'PhysicsRealityTutor/1.1 educational reader'})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read()
    for enc in ('utf-8-sig','utf-8','cp1252','latin-1'):
        try: return raw.decode(enc)
        except UnicodeDecodeError: pass
    return raw.decode('utf-8', errors='replace')


def strip_gutenberg(text: str) -> str:
    text = text.replace('\r\n','\n').replace('\r','\n')
    start = re.search(r'\*\*\* START OF (?:THIS|THE) PROJECT GUTENBERG EBOOK.*?\*\*\*', text, re.I)
    end = re.search(r'\*\*\* END OF (?:THIS|THE) PROJECT GUTENBERG EBOOK.*?\*\*\*', text, re.I)
    if start: text = text[start.end():]
    if end: text = text[:end.start()]
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()


def chunks_from_matches(text, pattern, title_fn, max_chars=14000):
    ms=list(re.finditer(pattern,text,re.M|re.I))
    if not ms: return chunk_plain(text, 'Reading', max_chars)
    out=[]
    for i,m in enumerate(ms):
        section=text[m.end(): ms[i+1].start() if i+1<len(ms) else len(text)].strip()
        title=title_fn(m)
        out.extend(chunk_plain(section,title,max_chars))
    return out


def chunk_plain(text, title, max_chars=14000):
    paras=[p.strip() for p in re.split(r'\n\s*\n',text) if p.strip()]
    out=[]; buf=[]; n=0; part=1
    for p in paras:
        if buf and n+len(p)>max_chars:
            out.append((title if part==1 else f'{title} — Part {part}', '\n\n'.join(buf)))
            buf=[]; n=0; part+=1
        buf.append(p); n+=len(p)+2
    if buf: out.append((title if part==1 else f'{title} — Part {part}', '\n\n'.join(buf)))
    return out


def split_book(text, kind):
    if kind=='aristotle':
        body=text[text.lower().find('part 1'):] if 'part 1' in text.lower() else text
        return chunks_from_matches(body, r'^\s*Part\s+(\d+)\s*$', lambda m:f'Part {m.group(1)}', 11000)
    if kind=='hume':
        # Gutenberg editions use either SECTION I. or SECTION 1.
        return chunks_from_matches(text, r'^\s*SECTION\s+([IVXLC]+|\d+)\.\s*$', lambda m:f'Section {m.group(1).upper()}', 13000)
    if kind=='berkeley':
        # Berkeley is paragraph-numbered; use readable groups while retaining every paragraph.
        start=re.search(r'OF THE PRINCIPLES OF HUMAN KNOWLEDGE', text, re.I)
        pre=text[:start.start()].strip() if start else ''
        body=text[start.end():].strip() if start else text
        out=[]
        if pre:
            # Keep Preface/Introduction as full source text, chunked if needed.
            out.extend(chunk_plain(pre,'Preface and Introduction',12000))
        marks=list(re.finditer(r'(?m)^\s*(\d+)\.\s+', body))
        if not marks:
            out.extend(chunk_plain(body,'Principles',12000)); return out
        group=[]
        for i,m in enumerate(marks):
            num=int(m.group(1)); seg=body[m.start(): marks[i+1].start() if i+1<len(marks) else len(body)].strip()
            group.append((num,seg))
            if len(group)>=12 or i==len(marks)-1:
                out.append((f'Principles §§{group[0][0]}–{group[-1][0]}','\n\n'.join(x[1] for x in group)))
                group=[]
        return out
    return chunk_plain(text,'Reading')


def main():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.exists(DB):
        raise SystemExit('Database not found. Run ./run.sh once first.')
    downloaded=[]
    for b in BOOKS:
        print(f"Downloading {b['title']} …")
        text=strip_gutenberg(download(b['url']))
        sections=split_book(text,b['split'])
        sections=[(t,c) for t,c in sections if len(c.strip())>100]
        if not sections: raise RuntimeError(f"Could not parse {b['title']}")
        print(f"  {len(text):,} characters → {len(sections)} reader sections")
        downloaded.append((b,sections))

    conn=sqlite3.connect(DB); ensure_reader_schema(conn)
    try:
        conn.execute('begin')
        for b,sections in downloaded:
            old_ids=[r[0] for r in conn.execute('select id from chapters where book_id=?',(b['id'],))]
            if old_ids:
                marks=','.join('?'*len(old_ids))
                for table in ('reading_progress','reading_attempts','bookmarks','reading_questions'):
                    conn.execute(f'delete from {table} where chapter_id in ({marks})',old_ids)
            conn.execute('delete from chapters where book_id=?',(b['id'],))
            conn.execute('''update books set title=?,author=?,description=?,source_note=?,is_full_text=1,source_url=?,reading_level=? where id=?''',
                         (b['title'],b['author'],b['description'],'Complete public-domain text imported from Project Gutenberg.',b['url'],b['reading_level'],b['id']))
            for pos,(title,content) in enumerate(sections,1):
                conn.execute('insert into chapters(book_id,position,title,content) values(?,?,?,?)',(b['id'],pos,title,content))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally: conn.close()
    print('\n✓ Full public-domain library imported.')
    print('Restart ./run.sh and open Library.')

if __name__=='__main__':
    try: main()
    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)
