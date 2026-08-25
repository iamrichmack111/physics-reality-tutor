from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, json
from datetime import datetime
from functools import wraps
from reader_migrations import ensure_reader_schema
from course_migrations import ensure_course_schema, ensure_autograde_schema, update_skill, schedule_review, award_competency, SKILL_BY_LESSON

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'data', 'physics_reality.db')
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-change-me-before-production')


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    ensure_reader_schema(conn)
    ensure_course_schema(conn)
    ensure_autograde_schema(conn)
    return conn


def logged_in(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if 'uid' not in session:
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return inner


def admin_only(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if session.get('role') != 'admin':
            abort(403)
        return fn(*args, **kwargs)
    return inner


def user_row():
    if 'uid' not in session: return None
    c=db(); r=c.execute('select * from users where id=?',(session['uid'],)).fetchone(); c.close(); return r

@app.context_processor
def inject_user(): return {'me': user_row()}

@app.get('/health')
def health():
    try:
        c = db()
        c.execute('select 1').fetchone()
        c.close()
        return {'app': 'Physics & Reality Tutor', 'status': 'ok'}, 200
    except Exception as exc:
        return {'app': 'Physics & Reality Tutor', 'status': 'error', 'detail': str(exc)}, 500

@app.route('/', methods=['GET'])
def root(): return redirect(url_for('dashboard') if 'uid' in session else url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        c=db(); u=c.execute('select * from users where username=? and active=1',(request.form['username'].strip(),)).fetchone(); c.close()
        if u and check_password_hash(u['password_hash'], request.form['password']):
            session.clear(); session.update(uid=u['id'], role=u['role'], username=u['username'])
            if u['must_change_password']:
                return redirect(url_for('change_password'))
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/change-password', methods=['GET','POST'])
@logged_in
def change_password():
    if request.method=='POST':
        p=request.form['password']; p2=request.form['confirm']
        if len(p)<8: flash('Use at least 8 characters.')
        elif p!=p2: flash('Passwords do not match.')
        else:
            c=db(); c.execute('update users set password_hash=?, must_change_password=0 where id=?',(generate_password_hash(p),session['uid'])); c.commit(); c.close(); flash('Password changed.'); return redirect(url_for('dashboard'))
    return render_template('change_password.html')

@app.route('/dashboard')
@logged_in
def dashboard():
    c=db();
    stats=c.execute('''select count(*) total, sum(case when completed=1 then 1 else 0 end) done,
                    round(avg(case when best_score is not null then best_score end),1) avgscore
                    from lesson_progress where user_id=?''',(session['uid'],)).fetchone()
    lessons=c.execute('''select l.*, coalesce(p.completed,0) completed, p.best_score from lessons l
        left join lesson_progress p on p.lesson_id=l.id and p.user_id=? order by l.position''',(session['uid'],)).fetchall()
    skills=c.execute('select * from skill_scores where user_id=? order by skill',(session['uid'],)).fetchall()
    due=c.execute("select count(*) from review_state where user_id=? and due_at<=?",(session['uid'],datetime.utcnow().isoformat())).fetchone()[0]
    cal=c.execute('select avg(abs(confidence - case when correct=1 then 100 else 0 end)) from confidence_answers where user_id=?',(session['uid'],)).fetchone()[0]
    calibration=round(max(0,100-(cal or 0)))
    # Self-paced recommendation: placement first, then reviews, vocabulary, then first unmastered lesson.
    next_activity=None
    diagnostic_done=bool(c.execute('select 1 from diagnostic_attempts where user_id=? limit 1',(session['uid'],)).fetchone())
    vocab_due=c.execute("select count(*) from vocabulary_terms v left join vocabulary_review r on r.term_id=v.id and r.user_id=? where r.due_at is null or r.due_at<=?",(session['uid'],datetime.utcnow().isoformat())).fetchone()[0]
    if not diagnostic_done:
        next_activity={'title':'Take your placement diagnostic','detail':'A short self-graded check sets your starting levels in ELA, Logic, Physics, and Math.','url':url_for('diagnostic')}
    elif due:
        next_activity={'title':f'{due} spaced review'+('s' if due!=1 else '')+' due','detail':'Strengthen retention before adding new material.','url':url_for('review')}
    elif vocab_due:
        next_activity={'title':f'{vocab_due} vocabulary item'+('s' if vocab_due!=1 else '')+' ready','detail':'Build the language needed for philosophy, science, and argument.','url':url_for('vocabulary')}
    else:
        nxt=next((x for x in lessons if not x['completed']),None)
        if nxt:
            next_activity={'title':f"Lesson {nxt['position']}: {nxt['title']}",'detail':nxt['question'],'url':url_for('lesson',lesson_id=nxt['id'])}
        else:
            next_activity={'title':'Transfer your mastery','detail':'Use experiments, debate, and writing to apply the course to unfamiliar claims.','url':url_for('experiments')}
    c.close()
    return render_template('dashboard.html', stats=stats, lessons=lessons, skills=skills,due_reviews=due,calibration=calibration,next_activity=next_activity,vocab_due=vocab_due,diagnostic_done=diagnostic_done)

@app.route('/lessons')
@logged_in
def lessons():
    c=db(); rows=c.execute('''select l.*,coalesce(p.completed,0) completed,p.best_score from lessons l left join lesson_progress p on p.lesson_id=l.id and p.user_id=? order by l.position''',(session['uid'],)).fetchall(); c.close(); return render_template('lessons.html',lessons=rows)

@app.route('/lesson/<int:lesson_id>')
@logged_in
def lesson(lesson_id):
    c=db(); l=c.execute('select * from lessons where id=?',(lesson_id,)).fetchone()
    if not l: c.close(); abort(404)
    defs=c.execute('select * from definitions where lesson_id=? order by id',(lesson_id,)).fetchall()
    proofs=c.execute('select * from proofs where lesson_id=? order by position',(lesson_id,)).fetchall()
    qs=c.execute('select id,prompt,options_json from questions where lesson_id=? order by id',(lesson_id,)).fetchall(); c.close()
    questions=[dict(q)|{'options':json.loads(q['options_json'])} for q in qs]
    animation_available=bool(l['animation_slug'] and os.path.exists(os.path.join(BASE,'static','animations',l['animation_slug']+'.mp4')))
    return render_template('lesson.html',lesson=l,definitions=defs,proofs=proofs,questions=questions,animation_available=animation_available)

@app.post('/lesson/<int:lesson_id>/grade')
@logged_in
def grade_lesson(lesson_id):
    c=db(); qs=c.execute('select * from questions where lesson_id=?',(lesson_id,)).fetchall(); correct=0; details=[]
    for q in qs:
        ans=request.form.get(f'q{q["id"]}','')
        ok=ans==q['correct_answer']; correct+=int(ok)
        confidence=int(request.form.get(f'c{q["id"]}','50'))
        c.execute('insert into confidence_answers(user_id,question_id,correct,confidence,created_at) values(?,?,?,?,?)',(session['uid'],q['id'],int(ok),confidence,datetime.utcnow().isoformat()))
        schedule_review(c,session['uid'],q['id'],ok)
        details.append({'prompt':q['prompt'],'answer':ans,'correct':q['correct_answer'],'ok':ok,'explanation':q['explanation'],'confidence':confidence})
    score=round((correct/len(qs))*100) if qs else 100
    row=c.execute('select * from lesson_progress where user_id=? and lesson_id=?',(session['uid'],lesson_id)).fetchone()
    completed=int(score>=80)
    if row:
        c.execute('update lesson_progress set attempts=attempts+1,best_score=max(coalesce(best_score,0),?),completed=max(completed,?),updated_at=? where user_id=? and lesson_id=?',(score,completed,datetime.utcnow().isoformat(),session['uid'],lesson_id))
    else:
        c.execute('insert into lesson_progress(user_id,lesson_id,attempts,best_score,completed,updated_at) values(?,?,?,?,?,?)',(session['uid'],lesson_id,1,score,completed,datetime.utcnow().isoformat()))
    c.execute('insert into attempts(user_id,lesson_id,score,created_at) values(?,?,?,?)',(session['uid'],lesson_id,score,datetime.utcnow().isoformat()))
    update_skill(c,session['uid'],SKILL_BY_LESSON.get(lesson_id,'Reasoning'),score)
    award_competency(c,session['uid'],'Logic','Lesson reasoning',max(1,score//20),f'lesson {lesson_id}')
    award_competency(c,session['uid'],'Physics','Concept mastery',max(1,score//25),f'lesson {lesson_id}')
    c.commit(); c.close(); return render_template('grade.html',score=score,details=details,lesson_id=lesson_id)

@app.route('/library')
@logged_in
def library():
    c=db()
    books=c.execute("""select b.*,
        count(ch.id) chapter_count,
        sum(case when rp.completed=1 then 1 else 0 end) completed_count
        from books b
        left join chapters ch on ch.book_id=b.id
        left join reading_progress rp on rp.chapter_id=ch.id and rp.user_id=?
        group by b.id order by b.id""",(session['uid'],)).fetchall()
    c.close()
    return render_template('library.html',books=books)

@app.route('/book/<int:book_id>')
@logged_in
def book(book_id):
    c=db()
    b=c.execute('select * from books where id=?',(book_id,)).fetchone()
    if not b:
        c.close(); abort(404)
    chapters=c.execute("""select ch.*,coalesce(rp.completed,0) completed,
        (select max(score) from reading_attempts ra where ra.user_id=? and ra.chapter_id=ch.id) best_score,
        exists(select 1 from bookmarks bm where bm.user_id=? and bm.chapter_id=ch.id) bookmarked
        from chapters ch
        left join reading_progress rp on rp.chapter_id=ch.id and rp.user_id=?
        where ch.book_id=? order by ch.position""",(session['uid'],session['uid'],session['uid'],book_id)).fetchall()
    completed=sum(int(x['completed']) for x in chapters)
    percent=round(completed/len(chapters)*100) if chapters else 0
    c.close()
    return render_template('book.html',book=b,chapters=chapters,completed=completed,percent=percent)

@app.route('/chapter/<int:chapter_id>')
@logged_in
def chapter(chapter_id):
    c=db()
    ch=c.execute("""select c.*,b.title book_title,b.author,b.id book_id,b.source_note,b.is_full_text
                    from chapters c join books b on b.id=c.book_id where c.id=?""",(chapter_id,)).fetchone()
    if not ch:
        c.close(); abort(404)
    prev_ch=c.execute('select id,title from chapters where book_id=? and position<? order by position desc limit 1',(ch['book_id'],ch['position'])).fetchone()
    next_ch=c.execute('select id,title from chapters where book_id=? and position>? order by position limit 1',(ch['book_id'],ch['position'])).fetchone()
    total=c.execute('select count(*) from chapters where book_id=?',(ch['book_id'],)).fetchone()[0]
    completed_count=c.execute("""select count(*) from reading_progress rp join chapters x on x.id=rp.chapter_id
                                 where rp.user_id=? and x.book_id=? and rp.completed=1""",(session['uid'],ch['book_id'])).fetchone()[0]
    progress=round(completed_count/total*100) if total else 0
    rq=c.execute('select * from reading_questions where chapter_id=? order by id',(chapter_id,)).fetchall()
    questions=[dict(q)|{'options':json.loads(q['options_json'])} for q in rq]
    rp=c.execute('select * from reading_progress where user_id=? and chapter_id=?',(session['uid'],chapter_id)).fetchone()
    best=c.execute('select max(score) from reading_attempts where user_id=? and chapter_id=?',(session['uid'],chapter_id)).fetchone()[0]
    bookmarked=bool(c.execute('select 1 from bookmarks where user_id=? and chapter_id=?',(session['uid'],chapter_id)).fetchone())
    c.execute("""insert into reading_progress(user_id,chapter_id,completed,last_read_at) values(?,?,0,?)
                 on conflict(user_id,chapter_id) do update set last_read_at=excluded.last_read_at""",(session['uid'],chapter_id,datetime.utcnow().isoformat()))
    c.commit(); c.close()
    return render_template('chapter.html',chapter=ch,prev_ch=prev_ch,next_ch=next_ch,total=total,
                           progress=progress,questions=questions,reading_progress=rp,best_score=best,bookmarked=bookmarked)

@app.post('/chapter/<int:chapter_id>/complete')
@logged_in
def complete_chapter(chapter_id):
    c=db()
    ch=c.execute('select id,book_id from chapters where id=?',(chapter_id,)).fetchone()
    if not ch: c.close(); abort(404)
    qcount=c.execute('select count(*) from reading_questions where chapter_id=?',(chapter_id,)).fetchone()[0]
    best=c.execute('select max(score) from reading_attempts where user_id=? and chapter_id=?',(session['uid'],chapter_id)).fetchone()[0]
    if qcount and (best is None or best < 80):
        c.close(); flash('Score at least 80% on the reading check before completing this section.')
        return redirect(url_for('chapter',chapter_id=chapter_id))
    c.execute("""insert into reading_progress(user_id,chapter_id,completed,last_read_at) values(?,?,1,?)
                 on conflict(user_id,chapter_id) do update set completed=1,last_read_at=excluded.last_read_at""",(session['uid'],chapter_id,datetime.utcnow().isoformat()))
    c.commit(); c.close(); flash('Reading section completed.')
    return redirect(url_for('chapter',chapter_id=chapter_id))

@app.post('/chapter/<int:chapter_id>/grade')
@logged_in
def grade_reading(chapter_id):
    c=db(); qs=c.execute('select * from reading_questions where chapter_id=? order by id',(chapter_id,)).fetchall()
    if not qs: c.close(); return redirect(url_for('chapter',chapter_id=chapter_id))
    correct=0
    for q in qs:
        correct += int(request.form.get(f'rq{q["id"]}','') == q['correct_answer'])
    score=round(correct/len(qs)*100)
    c.execute('insert into reading_attempts(user_id,chapter_id,score,created_at) values(?,?,?,?)',(session['uid'],chapter_id,score,datetime.utcnow().isoformat()))
    update_skill(c,session['uid'],'ELA Reading Comprehension',score)
    award_competency(c,session['uid'],'ELA','Reading comprehension',max(1,score//20),'reading check')
    award_competency(c,session['uid'],'Logic','Primary-source analysis',max(1,score//30),'reading check')
    if score>=80:
        c.execute("""insert into reading_progress(user_id,chapter_id,completed,last_read_at) values(?,?,1,?)
                     on conflict(user_id,chapter_id) do update set completed=1,last_read_at=excluded.last_read_at""",(session['uid'],chapter_id,datetime.utcnow().isoformat()))
        flash(f'Reading check: {score}%. Section mastered.')
    else:
        flash(f'Reading check: {score}%. Review the passage and try again; 80% is required.')
    c.commit(); c.close(); return redirect(url_for('chapter',chapter_id=chapter_id))

@app.post('/chapter/<int:chapter_id>/bookmark')
@logged_in
def toggle_bookmark(chapter_id):
    c=db(); exists=c.execute('select 1 from bookmarks where user_id=? and chapter_id=?',(session['uid'],chapter_id)).fetchone()
    if exists:
        c.execute('delete from bookmarks where user_id=? and chapter_id=?',(session['uid'],chapter_id))
    else:
        c.execute('insert into bookmarks(user_id,chapter_id,created_at) values(?,?,?)',(session['uid'],chapter_id,datetime.utcnow().isoformat()))
    c.commit(); c.close(); return redirect(url_for('chapter',chapter_id=chapter_id))

@app.route('/assignments')
@logged_in
def assignments():
    c=db(); a=c.execute('''select a.*, (select max(score) from assignment_attempts x where x.assignment_id=a.id and x.user_id=?) best_score from assignments a order by a.id''',(session['uid'],)).fetchall(); c.close(); return render_template('assignments.html',assignments=a)

@app.route('/assignment/<int:aid>',methods=['GET','POST'])
@logged_in
def assignment(aid):
    c=db(); a=c.execute('select * from assignments where id=?',(aid,)).fetchone(); qs=c.execute('select * from assignment_questions where assignment_id=? order by id',(aid,)).fetchall()
    if request.method=='POST':
        correct=0; feedback=[]
        for q in qs:
            ans=request.form.get(f'q{q["id"]}',''); ok=ans==q['correct_answer']; correct+=ok
            feedback.append((q,ans,ok))
        score=round(correct/len(qs)*100) if qs else 100
        c.execute('insert into assignment_attempts(user_id,assignment_id,score,created_at) values(?,?,?,?)',(session['uid'],aid,score,datetime.utcnow().isoformat()))
        award_competency(c,session['uid'],'Physics','Assignment mastery',max(1,score//25),f'assignment {aid}')
        award_competency(c,session['uid'],'ELA','Comprehension',max(1,score//30),f'assignment {aid}')
        c.commit(); c.close();
        return render_template('assignment_result.html',assignment=a,score=score,feedback=feedback)
    cooked=[dict(q)|{'options':json.loads(q['options_json'])} for q in qs]; c.close(); return render_template('assignment.html',assignment=a,questions=cooked)

@app.route('/debate/<int:lesson_id>')
@logged_in
def debate(lesson_id):
    c=db(); l=c.execute('select * from lessons where id=?',(lesson_id,)).fetchone(); defs=c.execute('select * from definitions where lesson_id=?',(lesson_id,)).fetchall(); proofs=c.execute('select * from proofs where lesson_id=? order by position',(lesson_id,)).fetchall(); c.close(); return render_template('debate.html',lesson=l,definitions=defs,proofs=proofs)

@app.route('/review',methods=['GET','POST'])
@logged_in
def review():
    c=db(); now=datetime.utcnow().isoformat()
    if request.method=='POST':
        qid=int(request.form['question_id']); q=c.execute('select * from questions where id=?',(qid,)).fetchone()
        ans=request.form.get('answer',''); ok=ans==q['correct_answer']; confidence=int(request.form.get('confidence','50'))
        schedule_review(c,session['uid'],qid,ok)
        c.execute('insert into confidence_answers(user_id,question_id,correct,confidence,created_at) values(?,?,?,?,?)',(session['uid'],qid,int(ok),confidence,datetime.utcnow().isoformat()))
        c.commit(); flash(('Correct. ' if ok else 'Not yet. ')+q['explanation']); c.close(); return redirect(url_for('review'))
    q=c.execute("""select q.*,l.title lesson_title from review_state r join questions q on q.id=r.question_id
        join lessons l on l.id=q.lesson_id where r.user_id=? and r.due_at<=? order by r.due_at limit 1""",(session['uid'],now)).fetchone()
    if not q:
        q=c.execute("""select q.*,l.title lesson_title from questions q join lessons l on l.id=q.lesson_id
            where not exists(select 1 from review_state r where r.user_id=? and r.question_id=q.id) order by q.id limit 1""",(session['uid'],)).fetchone()
    cooked=dict(q)|{'options':json.loads(q['options_json'])} if q else None
    c.close(); return render_template('review.html',q=cooked)

@app.route('/argument-builder/<int:lesson_id>',methods=['GET','POST'])
@logged_in
def argument_builder(lesson_id):
    c=db(); l=c.execute('select * from lessons where id=?',(lesson_id,)).fetchone(); proofs=c.execute('select * from proofs where lesson_id=? order by position',(lesson_id,)).fetchall()
    if not l: c.close(); abort(404)
    if request.method=='POST':
        major=request.form.get('major','').strip(); minor=request.form.get('minor','').strip(); conclusion=request.form.get('conclusion','').strip(); validity=request.form.get('validity',''); hidden=request.form.get('hidden_assumption','').strip()
        matching=any(major==p['major_premise'] and minor==p['minor_premise'] and conclusion==p['conclusion'] for p in proofs)
        score=(60 if matching else 0)+(20 if validity=='valid' else 0)+(20 if len(hidden)>=10 else 0)
        c.execute('insert into argument_attempts(user_id,lesson_id,major_text,minor_text,conclusion_text,validity,hidden_assumption,score,created_at) values(?,?,?,?,?,?,?,?,?)',(session['uid'],lesson_id,major,minor,conclusion,validity,hidden,score,datetime.utcnow().isoformat()))
        update_skill(c,session['uid'],'Argument Construction',score)
        award_competency(c,session['uid'],'Logic','Argument construction',max(1,score//15),f'argument builder {lesson_id}')
        award_competency(c,session['uid'],'ELA','Argument writing',max(1,score//25),f'argument builder {lesson_id}')
        c.commit(); flash(f'Argument structure score: {score}%.'); c.close(); return redirect(url_for('argument_builder',lesson_id=lesson_id))
    c.close(); return render_template('argument_builder.html',lesson=l,proofs=proofs)

@app.post('/debate/<int:lesson_id>/submit')
@logged_in
def debate_submit(lesson_id):
    required=['initial_position','initial_confidence','steelman','attack','switched_defense','final_position','final_confidence']
    if any(not request.form.get(k,'').strip() for k in required): flash('Complete every debate stage.'); return redirect(url_for('debate',lesson_id=lesson_id))
    c=db(); c.execute('''insert into debate_attempts(user_id,lesson_id,initial_position,initial_confidence,steelman,attack,switched_defense,final_position,final_confidence,completed,created_at) values(?,?,?,?,?,?,?,?,?,1,?)''',(
      session['uid'],lesson_id,request.form['initial_position'],int(request.form['initial_confidence']),request.form['steelman'],request.form['attack'],request.form['switched_defense'],request.form['final_position'],int(request.form['final_confidence']),datetime.utcnow().isoformat()))
    update_skill(c,session['uid'],'Steelman & Counterargument',90)
    award_competency(c,session['uid'],'Logic','Debate & steelman',6,f'debate {lesson_id}')
    award_competency(c,session['uid'],'ELA','Speaking & argument',5,f'debate {lesson_id}')
    c.commit(); c.close(); flash('Debate round completed. Side-switch recorded.'); return redirect(url_for('debate',lesson_id=lesson_id))

@app.route('/experiments')
@logged_in
def experiments(): return render_template('experiments.html')

@app.post('/experiments/measurement')
@logged_in
def record_measurement():
    c=db(); c.execute('''insert into lab_measurements(user_id,experiment_slug,variable_name,variable_value,observed_value,predicted_value,units,created_at) values(?,?,?,?,?,?,?,?)''',(session['uid'],request.form.get('experiment_slug','pendulum'),request.form.get('variable_name','length'),float(request.form.get('variable_value',0)),float(request.form['observed_value']) if request.form.get('observed_value') else None,float(request.form.get('predicted_value',0)),request.form.get('units','s'),datetime.utcnow().isoformat())); c.commit(); c.close(); return ('',204)

@app.route('/lab-notebook')
@logged_in
def lab_notebook():
    c=db(); entries=c.execute('select * from experiment_attempts where user_id=? order by id desc',(session['uid'],)).fetchall(); measurements=c.execute('select * from lab_measurements where user_id=? order by id desc limit 100',(session['uid'],)).fetchall(); c.close(); return render_template('lab_notebook.html',entries=entries,measurements=measurements)

@app.route('/ela',methods=['GET','POST'])
@logged_in
def ela():
    c=db()
    if request.method=='POST':
        response=request.form.get('response','').strip(); wc=len(response.split())
        c.execute('insert into ela_writing(user_id,kind,title,response,word_count,created_at) values(?,?,?,?,?,?)',(session['uid'],request.form.get('kind','Argument'),request.form.get('title','Untitled'),response,wc,datetime.utcnow().isoformat()))
        # Length is not quality, but sustained writing practice contributes modestly to the writing-practice metric.
        practice=min(100,40+wc//2); update_skill(c,session['uid'],'ELA Writing Practice',practice); c.commit(); flash(f'Writing saved to portfolio ({wc} words).')
        return redirect(url_for('ela'))
    reading=c.execute('select avg(score) from reading_attempts where user_id=?',(session['uid'],)).fetchone()[0] or 0
    arg=c.execute("select score from skill_scores where user_id=? and skill='Argument Construction'",(session['uid'],)).fetchone(); arg=arg[0] if arg else 0
    debate=c.execute("select score from skill_scores where user_id=? and skill='Steelman & Counterargument'",(session['uid'],)).fetchone(); debate=debate[0] if debate else 0
    evidence=c.execute("select score from skill_scores where user_id=? and skill='Evidence Evaluation'",(session['uid'],)).fetchone(); evidence=evidence[0] if evidence else 0
    wp=c.execute("select score from skill_scores where user_id=? and skill='ELA Writing Practice'",(session['uid'],)).fetchone(); wp=wp[0] if wp else 0
    ela_scores={'Reading comprehension':round(reading),'Argument structure':arg,'Evidence & source reasoning':evidence,'Speaking / debate reasoning':debate,'Writing practice':wp}
    writing=c.execute('select * from ela_writing where user_id=? order by id desc',(session['uid'],)).fetchall(); c.close(); return render_template('ela.html',ela_scores=ela_scores,writing=writing)

@app.post('/experiments/record')
@logged_in
def record_experiment():
    c=db(); c.execute('insert into experiment_attempts(user_id,experiment_slug,prediction,observation,interpretation,created_at) values(?,?,?,?,?,?)',(session['uid'],request.form['experiment_slug'],request.form['prediction'],request.form['observation'],request.form['interpretation'],datetime.utcnow().isoformat()))
    update_skill(c,session['uid'],'Prediction & Evidence',90)
    award_competency(c,session['uid'],'Physics','Experimental reasoning',6,request.form['experiment_slug'])
    award_competency(c,session['uid'],'Logic','Observation vs interpretation',5,request.form['experiment_slug'])
    award_competency(c,session['uid'],'ELA','Lab writing',4,request.form['experiment_slug'])
    words=len((request.form['prediction']+' '+request.form['observation']+' '+request.form['interpretation']).split())
    update_skill(c,session['uid'],'ELA Writing Practice',min(100,45+words//2))
    c.commit(); c.close(); flash('Experiment journal saved to your Lab Notebook.'); return redirect(url_for('experiments'))


def auto_grade_writing(text, citation_count=0):
    low=text.lower(); wc=len(text.split())
    claim=any(x in low for x in ['i argue','the proposition','my claim','i contend','this shows'])
    evidence=any(x in low for x in ['evidence','data','according to','the experiment','the passage','the source']) or citation_count>0
    counter=any(x in low for x in ['however','although','counterargument','opposing','on the other hand'])
    conclusion=any(x in low for x in ['therefore','in conclusion','thus','for these reasons'])
    explanation=any(x in low for x in ['because','therefore','which means','this suggests','this supports'])
    length_score=20 if wc>=180 else 15 if wc>=120 else 10 if wc>=70 else 5 if wc>=35 else 0
    rubric={
      'Sustained response':length_score,
      'Clear claim / proposition':20 if claim else 0,
      'Evidence or source use':20 if evidence else 0,
      'Reasoning connects evidence to claim':15 if explanation else 0,
      'Counterargument / qualification':15 if counter else 0,
      'Conclusion':10 if conclusion else 0,
    }
    return sum(rubric.values()), rubric

@app.route('/diagnostic',methods=['GET','POST'])
@logged_in
def diagnostic():
    c=db(); qs=c.execute('select * from diagnostic_questions order by domain,id').fetchall()
    if request.method=='POST':
        domains={}; total=0
        for q in qs:
            ok=request.form.get(f'd{q["id"]}','')==q['correct_answer']; total+=int(ok)
            domains.setdefault(q['domain'],[0,0]); domains[q['domain']][0]+=int(ok); domains[q['domain']][1]+=1
        scores={k:round(v[0]/v[1]*100) for k,v in domains.items()}
        overall=round(total/len(qs)*100) if qs else 0
        c.execute('insert into diagnostic_attempts(user_id,total_score,domain_scores_json,created_at) values(?,?,?,?)',
                  (session['uid'],overall,json.dumps(scores),datetime.utcnow().isoformat()))
        for domain,score in scores.items():
            update_skill(c,session['uid'],f'{domain} Diagnostic',score)
            award_competency(c,session['uid'],domain,'Diagnostic placement',max(1,score//10),'diagnostic')
        c.commit(); c.close(); return render_template('diagnostic_result.html',overall=overall,scores=scores)
    cooked=[dict(q)|{'options':json.loads(q['options_json'])} for q in qs]
    latest=c.execute('select * from diagnostic_attempts where user_id=? order by id desc limit 1',(session['uid'],)).fetchone(); c.close()
    return render_template('diagnostic.html',questions=cooked,latest=latest)

@app.route('/vocabulary',methods=['GET','POST'])
@logged_in
def vocabulary():
    c=db()
    if request.method=='POST':
        tid=int(request.form['term_id']); term=c.execute('select * from vocabulary_terms where id=?',(tid,)).fetchone()
        chosen=request.form.get('definition',''); ok=chosen==term['definition']
        row=c.execute('select * from vocabulary_review where user_id=? and term_id=?',(session['uid'],tid)).fetchone()
        from datetime import timedelta
        correct=(row['correct_count'] if row else 0)+int(ok); incorrect=(row['incorrect_count'] if row else 0)+int(not ok)
        days=7 if correct>=3 and ok else 3 if ok else 1
        due=(datetime.utcnow()+timedelta(days=days)).isoformat()
        c.execute('insert into vocabulary_review(user_id,term_id,correct_count,incorrect_count,due_at,last_result) values(?,?,?,?,?,?) on conflict(user_id,term_id) do update set correct_count=excluded.correct_count,incorrect_count=excluded.incorrect_count,due_at=excluded.due_at,last_result=excluded.last_result',
          (session['uid'],tid,correct,incorrect,due,int(ok)))
        update_skill(c,session['uid'],'ELA Vocabulary',100 if ok else 35)
        award_competency(c,session['uid'],'ELA','Vocabulary',2 if ok else 1,'vocabulary')
        c.commit(); flash(('Correct. ' if ok else 'Not yet. ')+term['term']+': '+term['definition']); c.close(); return redirect(url_for('vocabulary'))
    now=datetime.utcnow().isoformat()
    term=c.execute('select v.* from vocabulary_terms v left join vocabulary_review r on r.term_id=v.id and r.user_id=? where r.due_at is null or r.due_at<=? order by coalesce(r.incorrect_count,0) desc,v.id limit 1',(session['uid'],now)).fetchone()
    options=[]
    if term:
        defs=[r[0] for r in c.execute('select definition from vocabulary_terms where id<>? order by random() limit 3',(term['id'],)).fetchall()]
        options=defs+[term['definition']]
        options=sorted(options,key=lambda x: sum(ord(ch) for ch in x)%97)
    stats=c.execute('select count(*) total, sum(case when correct_count>=3 then 1 else 0 end) mastered from vocabulary_review where user_id=?',(session['uid'],)).fetchone(); c.close()
    return render_template('vocabulary.html',term=term,options=options,stats=stats)

@app.route('/evidence',methods=['GET','POST'])
@logged_in
def evidence():
    c=db()
    if request.method=='POST':
        title=request.form.get('title','').strip(); side=request.form.get('claim_side','Neutral'); st=request.form.get('source_type','Other')
        citation=request.form.get('citation','').strip(); text=request.form.get('evidence_text','').strip(); note=request.form.get('relevance_note','').strip()
        source_points={'Primary source':35,'Experiment / data':35,'Scientific reference':30,'Textbook':25,'Secondary source':20,'Opinion / anecdote':8,'Other':10}.get(st,10)
        score=min(100,source_points+(20 if len(citation)>=12 else 0)+(25 if len(text)>=40 else 10 if text else 0)+(20 if len(note)>=30 else 8 if note else 0))
        c.execute('insert into evidence_locker(user_id,title,claim_side,source_type,citation,evidence_text,relevance_note,quality_score,created_at) values(?,?,?,?,?,?,?,?,?)',
                  (session['uid'],title,side,st,citation,text,note,score,datetime.utcnow().isoformat()))
        update_skill(c,session['uid'],'Evidence & Source Reasoning',score)
        award_competency(c,session['uid'],'ELA','Source evaluation',max(1,score//20),'evidence locker')
        award_competency(c,session['uid'],'Logic','Evidence evaluation',max(1,score//25),'evidence locker')
        c.commit(); flash(f'Evidence saved. Completeness/source-quality rubric: {score}%.'); return redirect(url_for('evidence'))
    items=c.execute('select * from evidence_locker where user_id=? order by id desc',(session['uid'],)).fetchall(); c.close(); return render_template('evidence.html',items=items)

@app.route('/writing-lab',methods=['GET','POST'])
@logged_in
def writing_lab():
    c=db()
    if request.method=='POST':
        text=request.form.get('response','').strip(); title=request.form.get('title','Untitled').strip(); kind=request.form.get('kind','Argument'); stage=request.form.get('stage','Draft')
        citations=int(request.form.get('citation_count','0') or 0); score,rubric=auto_grade_writing(text,citations)
        c.execute('insert into writing_submissions(user_id,title,kind,stage,response,word_count,citation_count,auto_score,rubric_json,created_at) values(?,?,?,?,?,?,?,?,?,?)',
                  (session['uid'],title,kind,stage,text,len(text.split()),citations,score,json.dumps(rubric),datetime.utcnow().isoformat()))
        update_skill(c,session['uid'],'ELA Writing Structure',score)
        award_competency(c,session['uid'],'ELA','Writing',max(1,score//15),'writing lab')
        award_competency(c,session['uid'],'Logic','Argument communication',max(1,score//25),'writing lab')
        c.commit(); flash(f'Rubric score: {score}%. This grades structure/completeness, not whether the conclusion is true.'); return redirect(url_for('writing_lab'))
    rows=c.execute('select * from writing_submissions where user_id=? order by id desc',(session['uid'],)).fetchall(); submissions=[]
    for r in rows: submissions.append(dict(r)|{'rubric':json.loads(r['rubric_json'])})
    c.close(); return render_template('writing_lab.html',submissions=submissions)

@app.route('/mastery')
@logged_in
def mastery():
    c=db(); rows=c.execute('select subject,skill,sum(points) points from competency_events where user_id=? group by subject,skill order by subject,points desc',(session['uid'],)).fetchall()
    subjects={}
    for r in rows: subjects.setdefault(r['subject'],[]).append(r)
    skills=c.execute('select * from skill_scores where user_id=? order by skill',(session['uid'],)).fetchall(); c.close(); return render_template('mastery.html',subjects=subjects,skills=skills)

@app.route('/admin')
@logged_in
@admin_only
def admin():
    c=db(); users=c.execute('select id,username,display_name,role,active,must_change_password from users order by id').fetchall(); counts={
        'users':c.execute('select count(*) from users').fetchone()[0], 'lessons':c.execute('select count(*) from lessons').fetchone()[0], 'assignments':c.execute('select count(*) from assignments').fetchone()[0]}; c.close(); return render_template('admin.html',users=users,counts=counts)

@app.post('/admin/users/create')
@logged_in
@admin_only
def admin_create_user():
    username=request.form['username'].strip(); pw=request.form.get('password','changeme123'); display=request.form.get('display_name',username).strip(); role=request.form.get('role','student')
    c=db()
    try:
        c.execute('insert into users(username,password_hash,display_name,role,active,must_change_password) values(?,?,?,?,1,1)',(username,generate_password_hash(pw),display,role)); c.commit(); flash('Account created.')
    except sqlite3.IntegrityError: flash('Username already exists.')
    c.close(); return redirect(url_for('admin'))

@app.post('/admin/users/<int:uid>/reset')
@logged_in
@admin_only
def admin_reset(uid):
    pw=request.form.get('password','changeme123'); c=db(); c.execute('update users set password_hash=?,must_change_password=1 where id=?',(generate_password_hash(pw),uid)); c.commit(); c.close(); flash('Password reset; user must change it at next login.'); return redirect(url_for('admin'))

@app.post('/admin/users/<int:uid>/toggle')
@logged_in
@admin_only
def admin_toggle(uid):
    if uid==session['uid']: flash('You cannot disable your own account.'); return redirect(url_for('admin'))
    c=db(); c.execute('update users set active=case active when 1 then 0 else 1 end where id=?',(uid,)); c.commit(); c.close(); return redirect(url_for('admin'))

@app.post('/admin/users/<int:uid>/progress/reset')
@logged_in
@admin_only
def admin_reset_progress(uid):
    c=db();
    for table in ('lesson_progress','attempts','assignment_attempts','reading_progress','skill_scores','review_state','debate_attempts','argument_attempts','experiment_attempts','confidence_answers','lab_measurements','ela_writing','source_annotations','diagnostic_attempts','vocabulary_review','evidence_locker','writing_submissions','competency_events'):
        c.execute(f'delete from {table} where user_id=?',(uid,))
    c.commit(); c.close(); flash('Student progress reset.'); return redirect(url_for('admin'))

@app.route('/admin/content')
@logged_in
@admin_only
def admin_content():
    c=db(); lessons=c.execute('select * from lessons order by position').fetchall(); c.close(); return render_template('admin_content.html',lessons=lessons)

@app.post('/admin/content/lesson')
@logged_in
@admin_only
def admin_add_lesson():
    c=db(); pos=c.execute('select coalesce(max(position),0)+1 from lessons').fetchone()[0]
    c.execute('''insert into lessons(title,unit,position,question,proposition,counter_proposition,restatement,reading,animation_slug) values(?,?,?,?,?,?,?,?,?)''',(
        request.form['title'],request.form.get('unit','Custom'),pos,request.form.get('question',''),request.form.get('proposition',''),request.form.get('counter_proposition',''),request.form.get('restatement',''),request.form.get('reading',''),request.form.get('animation_slug','')))
    c.commit(); c.close(); flash('Lesson added.'); return redirect(url_for('admin_content'))

if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5088)), debug=False)
