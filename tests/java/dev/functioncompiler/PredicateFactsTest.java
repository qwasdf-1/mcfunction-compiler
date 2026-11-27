package dev.functioncompiler;

import java.util.List;
import static dev.functioncompiler.PredicateFacts.*;

public final class PredicateFactsTest {
    private static int checks;
    private static void expect(Outcome actual, Outcome expected) {
        checks++;
        if (actual != expected) throw new AssertionError(actual + " != " + expected);
    }
    public static void main(String[] args) {
        Flow f = new Flow();
        expect(f.range(0,"5..",false),Outcome.UNKNOWN);
        expect(f.range(0,"1..",false),Outcome.PASS);
        expect(f.range(0,"..4",true),Outcome.PASS);
        expect(f.range(0,"..4",false),Outcome.FAIL);
        f = new Flow();
        expect(f.range(0,"5..8",false),Outcome.UNKNOWN);
        expect(f.range(0,"6..10",false),Outcome.UNKNOWN);
        expect(f.range(0,"6..8",false),Outcome.PASS);
        f = new Flow();
        expect(f.range(0,"-2147483648..2147483647",true),Outcome.UNKNOWN);
        expect(f.comparison(0,0,EQ,true),Outcome.PASS);
        expect(f.range(0,"0",false),Outcome.FAIL);
        f = new Flow();
        expect(f.comparison(0,1,LT,false),Outcome.UNKNOWN);
        expect(f.comparison(1,0,GT,false),Outcome.PASS);
        expect(f.comparison(0,1,LT|EQ,false),Outcome.PASS);
        expect(f.comparison(0,1,EQ,false),Outcome.FAIL);
        f = new Flow();
        expect(f.comparison(0,1,LT,true),Outcome.UNKNOWN);
        expect(f.comparison(1,0,GT,true),Outcome.PASS);
        expect(f.comparison(0,1,EQ|GT,false),Outcome.UNKNOWN); // absent remains possible
        f = new Flow();
        expect(f.range(0,"2147483647..",false),Outcome.UNKNOWN);
        expect(f.range(0,"..2147483646",true),Outcome.PASS);
        f = new Flow();
        expect(f.range(0,"..-2147483648",false),Outcome.UNKNOWN);
        expect(f.range(0,"-2147483648",false),Outcome.PASS);
        // Independent concrete oracle for ranges over representative endpoint
        // partitions and absence, including complemented nonconvex domains.
        var ranges = List.of("-2..2","-1..","..0","0","1..3","-2147483648..2147483647");
        Integer[] samples = {null,Integer.MIN_VALUE,-3,-2,-1,0,1,2,3,4,Integer.MAX_VALUE};
        for (String a:ranges) for (boolean na:new boolean[]{false,true})
            for (String b:ranges) for (boolean nb:new boolean[]{false,true}) {
                f = new Flow(); f.range(0,a,na);
                Outcome outcome = f.range(0,b,nb);
                for (Integer v:samples) if (matches(a,v)!=na) {
                    boolean pass = matches(b,v)!=nb;
                    checks++;
                    if ((outcome==Outcome.PASS&&!pass)||(outcome==Outcome.FAIL&&pass))
                        throw new AssertionError("unsound range proof");
                }
            }
        System.out.println("IR040_PREDICATE_FACTS checks="+checks);
    }
    private static boolean matches(String r,Integer v) {
        if(v==null)return false;
        int i=r.indexOf("..");
        if(i<0)return v==Integer.parseInt(r);
        return (i==0||v>=Integer.parseInt(r.substring(0,i)))
            &&(i+2==r.length()||v<=Integer.parseInt(r.substring(i+2)));
    }
}
