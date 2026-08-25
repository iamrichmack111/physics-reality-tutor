from manim import *

class Definitions(Scene):
    def construct(self):
        title=Text('Agree on Definitions').scale(.8).to_edge(UP)
        terms=VGroup(*[Text(x).scale(.5) for x in ['Observer','Measurement','Evidence','Reality']]).arrange(DOWN,buff=.5)
        self.play(Write(title)); self.play(LaggedStart(*[FadeIn(x) for x in terms],lag_ratio=.25)); self.wait(1)
        box=SurroundingRectangle(terms,buff=.3); self.play(Create(box)); self.wait(1)

class Syllogism(Scene):
    def construct(self):
        major=Text('Major Premise').scale(.55).shift(UP*2)
        minor=Text('Minor Premise').scale(.55)
        conclusion=Text('Conclusion').scale(.6).shift(DOWN*2)
        a1=Arrow(major.get_bottom(),minor.get_top()); a2=Arrow(minor.get_bottom(),conclusion.get_top())
        self.play(Write(major)); self.play(GrowArrow(a1),Write(minor)); self.play(GrowArrow(a2),Write(conclusion)); self.wait(2)

class LimitedRendering(Scene):
    def construct(self):
        title=Text('Limited Rendering: Analogy, Not Proof').scale(.65).to_edge(UP)
        dots=VGroup(*[Dot(radius=.045) for _ in range(80)]).arrange_in_grid(rows=8,cols=10,buff=.25).scale(1.2)
        focus=Circle(radius=1.25).move_to(dots[44])
        label=Text('Interaction / measurement').scale(.42).next_to(focus,DOWN)
        self.play(Write(title),FadeIn(dots)); self.play(Create(focus),Write(label)); self.play(dots[33].animate.scale(3),dots[34].animate.scale(3),dots[43].animate.scale(3),dots[44].animate.scale(3)); self.wait(2)

class Information(Scene):
    def construct(self):
        title=Text('Matter ↔ Information?').to_edge(UP)
        left=Square(2).shift(LEFT*2); right=Square(2).shift(RIGHT*2)
        l=Text('Physical\nState').scale(.5).move_to(left); r=Text('Information').scale(.5).move_to(right)
        arrows=VGroup(Arrow(left.get_right(),right.get_left()),Arrow(right.get_left()+DOWN*.4,left.get_right()+DOWN*.4))
        self.play(Write(title),Create(left),Create(right),Write(l),Write(r)); self.play(Create(arrows)); self.wait(2)

class MathematicalUniverse(Scene):
    def construct(self):
        eq=MathTex(r'F=ma').scale(1.4); orbit=Circle(2); dot=Dot(orbit.point_at_angle(0))
        self.play(Write(eq)); self.play(eq.animate.to_edge(UP),Create(orbit)); self.play(MoveAlongPath(dot,orbit),run_time=3,rate_func=linear); self.wait(1)

class Simulation(Scene):
    def construct(self):
        claim=Text('Possible ≠ Proven').scale(.9)
        possible=Text('Logical possibility').scale(.5).shift(LEFT*3+DOWN*2)
        evidence=Text('Evidence').scale(.5).shift(DOWN*2)
        proof=Text('Established').scale(.5).shift(RIGHT*3+DOWN*2)
        self.play(Write(claim)); self.play(claim.animate.to_edge(UP)); self.play(Write(possible),Write(evidence),Write(proof)); self.play(Create(Arrow(possible.get_right(),evidence.get_left())),Create(Arrow(evidence.get_right(),proof.get_left()))); self.wait(2)
