package dev.functioncompiler;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * IR-040: a pure, ordered predicate abstract interpreter. Integer ranges are
 * unions of closed intervals plus a distinguished ABSENT value. Comparisons
 * use LT/EQ/GT/ABSENT relation masks. Facts are conditional on the path having
 * passed every preceding guard. Never infer a literal holder aliases @s.
 */
final class PredicateFacts {
    private PredicateFacts() {}
    static final int LT = 1, EQ = 2, GT = 4, ABSENT = 8, ALL = 15;
    enum Outcome { UNKNOWN, PASS, FAIL }
    record Interval(long lo, long hi) {
        Interval {
            if (lo > hi || lo < Integer.MIN_VALUE || hi > Integer.MAX_VALUE)
                throw new IllegalArgumentException("bad interval");
        }
    }
    record Domain(List<Interval> intervals, boolean absent) {
        Domain { intervals = List.copyOf(intervals); }
        static Domain all() {
            return new Domain(List.of(new Interval(Integer.MIN_VALUE, Integer.MAX_VALUE)), true);
        }
        static Domain range(String text, boolean unless) {
            int i = text.indexOf("..");
            long lo = i < 0 ? Integer.parseInt(text) : i == 0
                    ? Integer.MIN_VALUE : Integer.parseInt(text.substring(0, i));
            long hi = i < 0 ? lo : i + 2 == text.length()
                    ? Integer.MAX_VALUE : Integer.parseInt(text.substring(i + 2));
            if (lo > hi) throw new IllegalArgumentException("invalid range");
            if (!unless) return new Domain(List.of(new Interval(lo, hi)), false);
            List<Interval> complement = new ArrayList<>();
            if (lo > Integer.MIN_VALUE) complement.add(new Interval(Integer.MIN_VALUE, lo - 1));
            if (hi < Integer.MAX_VALUE) complement.add(new Interval(hi + 1, Integer.MAX_VALUE));
            return new Domain(complement, true);
        }
        Domain intersect(Domain other) {
            List<Interval> result = new ArrayList<>();
            for (Interval a : intervals) for (Interval b : other.intervals) {
                long lo = Math.max(a.lo, b.lo), hi = Math.min(a.hi, b.hi);
                if (lo <= hi) result.add(new Interval(lo, hi));
            }
            return new Domain(result, absent && other.absent);
        }
        boolean empty() { return intervals.isEmpty() && !absent; }
        Domain present() { return new Domain(intervals, false); }
    }
    record Pair(int left, int right) {}
    static final class Flow {
        private final Map<Integer, Domain> values = new HashMap<>();
        private final Map<Pair, Integer> relations = new HashMap<>();
        Domain domain(int slot) { return values.getOrDefault(slot, Domain.all()); }

        Outcome range(int slot, String range, boolean unless) {
            Domain prior = domain(slot);
            Domain accepted = prior.intersect(Domain.range(range, unless));
            Domain rejected = prior.intersect(Domain.range(range, !unless));
            values.put(slot, accepted);
            return accepted.empty() ? Outcome.FAIL : rejected.empty() ? Outcome.PASS : Outcome.UNKNOWN;
        }

        Outcome comparison(int left, int right, int mask, boolean unless) {
            if (left > right) {
                int tmp = left; left = right; right = tmp;
                mask = (mask & EQ) | ((mask & LT) != 0 ? GT : 0)
                        | ((mask & GT) != 0 ? LT : 0);
            }
            Pair pair = new Pair(left, right);
            int prior = relations.getOrDefault(pair, left == right ? EQ | ABSENT : ALL);
            Domain a = domain(left), b = domain(right);
            if (!a.absent && !b.absent) prior &= ~ABSENT;
            if (a.intervals.isEmpty() || b.intervals.isEmpty()) prior &= ABSENT;
            int allowed = unless ? ALL ^ mask : mask;
            int accepted = prior & allowed;
            int rejected = prior & (ALL ^ allowed);
            relations.put(pair, accepted);
            if ((accepted & ABSENT) == 0) {
                values.put(left, a.present());
                values.put(right, b.present());
            }
            return accepted == 0 ? Outcome.FAIL : rejected == 0 ? Outcome.PASS : Outcome.UNKNOWN;
        }
    }
}
