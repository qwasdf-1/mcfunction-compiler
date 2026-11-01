package dev.functioncompiler;

import net.minecraft.commands.execution.ExecutionContext;

import java.util.ArrayDeque;
import java.util.Deque;

public final class ExecutionContextBridge {
    private static final ThreadLocal<Deque<ExecutionContext<?>>> STACK =
            ThreadLocal.withInitial(ArrayDeque::new);

    private ExecutionContextBridge() {
    }

    public static void push(ExecutionContext<?> context) {
        STACK.get().push(context);
    }

    public static void pop() {
        Deque<ExecutionContext<?>> stack = STACK.get();
        if (!stack.isEmpty()) {
            stack.pop();
            if (stack.isEmpty()) {
                STACK.remove();
            }
        }
    }

    public static <T> ExecutionContext<T> currentContext() {
        Deque<ExecutionContext<?>> stack = STACK.get();
        if (stack.isEmpty()) {
            return null;
        }
        @SuppressWarnings("unchecked")
        ExecutionContext<T> context = (ExecutionContext<T>) stack.peek();
        return context;
    }
}
