package dev.functioncompiler;

import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.execution.UnboundEntryAction;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.Label;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.util.concurrent.atomic.AtomicLong;

/**
 * IR-008 direct semantic lowering, NOT the older executeStep bridge.
 *
 * Each accepted score instruction emits a direct INVOKEINTERFACE to
 * ScoreAccess.add/set; the only helper calls perform vanilla bookkeeping,
 * dynamic objective guards and return feedback. The emitted action remains
 * a vanilla UnboundEntryAction, so unsupported entries keep their original
 * scheduler positions and rollback happens before any execution.
 */
final class TypedScoreIRBytecode implements Opcodes {
    private static final AtomicLong CLASSES = new AtomicLong();
    private static final String ACTION = "net/minecraft/commands/execution/UnboundEntryAction";
    private static final String SOURCE = "net/minecraft/commands/CommandSourceStack";
    private static final String CONTEXT = "net/minecraft/commands/execution/ExecutionContext";
    private static final String FRAME = "net/minecraft/commands/execution/Frame";
    private static final String SCORE = "net/minecraft/world/scores/ScoreAccess";
    private static final String INSTRUCTION = "dev/functioncompiler/TypedScoreIR$Instruction";
    private static final String STATE = "dev/functioncompiler/TypedScoreIRRuntime$State";
    private static final String STEPS = "[L" + INSTRUCTION + ";";
    private static final String EXECUTE = "(Ljava/lang/Object;L" + CONTEXT + ";L" + FRAME + ";)V";

    private TypedScoreIRBytecode() {}

    @SuppressWarnings("unchecked")
    static UnboundEntryAction<CommandSourceStack> emit(TypedScoreIR.Program program) {
        String internal = "dev/functioncompiler/TypedScoreIR$Generated$" + CLASSES.incrementAndGet();
        byte[] bytes = generate(internal, program);
        try {
            MethodHandles.Lookup lookup = MethodHandles.lookup().defineHiddenClass(
                    bytes, true, MethodHandles.Lookup.ClassOption.NESTMATE);
            var constructor = lookup.findConstructor(
                    lookup.lookupClass(),
                    MethodType.methodType(void.class, TypedScoreIR.Instruction[].class));
            return (UnboundEntryAction<CommandSourceStack>) constructor.invoke(
                    (Object) program.instructions().toArray(TypedScoreIR.Instruction[]::new));
        } catch (Throwable failure) {
            if (failure instanceof Error error) throw error;
            if (failure instanceof RuntimeException runtime) throw runtime;
            throw new IllegalStateException("IR-008 generated class couldn't load", failure);
        }
    }

    private static byte[] generate(String internal, TypedScoreIR.Program program) {
        ClassWriter writer = new ClassWriter(ClassWriter.COMPUTE_FRAMES | ClassWriter.COMPUTE_MAXS);
        writer.visit(V17, ACC_FINAL | ACC_SUPER, internal, null, "java/lang/Object",
                new String[]{ACTION});
        writer.visitField(ACC_PRIVATE | ACC_FINAL, "steps", STEPS, null, null).visitEnd();

        MethodVisitor ctor = writer.visitMethod(ACC_PUBLIC, "<init>", "(" + STEPS + ")V",
                null, null);
        ctor.visitCode();
        ctor.visitVarInsn(ALOAD, 0);
        ctor.visitMethodInsn(INVOKESPECIAL, "java/lang/Object", "<init>", "()V", false);
        ctor.visitVarInsn(ALOAD, 0);
        ctor.visitVarInsn(ALOAD, 1);
        ctor.visitFieldInsn(PUTFIELD, internal, "steps", STEPS);
        ctor.visitInsn(RETURN);
        ctor.visitMaxs(0, 0);
        ctor.visitEnd();

        MethodVisitor method = writer.visitMethod(ACC_PUBLIC, "execute", EXECUTE,
                null, null);
        method.visitCode();
        // Local 4: source; 5: one reusable invocation-state; 6: decision;
        // 7: new score. No allocation for an individual IR instruction.
        method.visitVarInsn(ALOAD, 1);
        method.visitTypeInsn(CHECKCAST, SOURCE);
        method.visitVarInsn(ASTORE, 4);
        method.visitTypeInsn(NEW, STATE);
        method.visitInsn(DUP);
        method.visitVarInsn(ALOAD, 4);
        method.visitVarInsn(ALOAD, 2);
        method.visitVarInsn(ALOAD, 3);
        method.visitMethodInsn(INVOKESPECIAL, STATE, "<init>",
                "(L" + SOURCE + ";L" + CONTEXT + ";L" + FRAME + ";)V", false);
        method.visitVarInsn(ASTORE, 5);

        method.visitMethodInsn(INVOKESTATIC, "dev/functioncompiler/TypedScoreIR",
                "executed", "()V", false);
        Label done = new Label();
        for (int index = 0; index < program.instructions().size(); index++) {
            TypedScoreIR.Instruction instruction = program.instructions().get(index);
            Label next = new Label();

            method.visitVarInsn(ALOAD, 5);
            method.visitVarInsn(ALOAD, 0);
            method.visitFieldInsn(GETFIELD, internal, "steps", STEPS);
            pushInt(method, index);
            method.visitInsn(AALOAD);
            method.visitMethodInsn(INVOKEVIRTUAL, STATE, "begin",
                    "(L" + INSTRUCTION + ";)I", false);
            method.visitVarInsn(ISTORE, 6);

            method.visitVarInsn(ILOAD, 6);
            method.visitJumpInsn(IFEQ, done);
            method.visitVarInsn(ILOAD, 6);
            method.visitInsn(ICONST_2);
            method.visitJumpInsn(IF_ICMPEQ, next);

            method.visitVarInsn(ALOAD, 5);
            method.visitMethodInsn(INVOKEVIRTUAL, STATE, "access",
                    "()L" + SCORE + ";", false);
            int amount = instruction.amount();
            switch (instruction.operation()) {
                case ADD, REMOVE -> {
                    pushInt(method, instruction.operation() == ScoreAddCommand.Operation.REMOVE
                            ? -amount : amount);
                    method.visitMethodInsn(INVOKEINTERFACE, SCORE, "add", "(I)I", true);
                    method.visitVarInsn(ISTORE, 7);
                }
                case SET -> {
                    pushInt(method, amount);
                    method.visitMethodInsn(INVOKEINTERFACE, SCORE, "set", "(I)V", true);
                    pushInt(method, amount);
                    method.visitVarInsn(ISTORE, 7);
                }
            }

            method.visitVarInsn(ALOAD, 5);
            method.visitVarInsn(ILOAD, 7);
            method.visitMethodInsn(INVOKEVIRTUAL, STATE, "finish", "(I)V", false);
            method.visitLabel(next);
        }
        method.visitLabel(done);
        method.visitInsn(RETURN);
        method.visitMaxs(0, 0);
        method.visitEnd();
        writer.visitEnd();
        return writer.toByteArray();
    }

    private static void pushInt(MethodVisitor method, int value) {
        if (value >= -1 && value <= 5) {
            method.visitInsn(ICONST_0 + value);
        } else if (value >= Byte.MIN_VALUE && value <= Byte.MAX_VALUE) {
            method.visitIntInsn(BIPUSH, value);
        } else if (value >= Short.MIN_VALUE && value <= Short.MAX_VALUE) {
            method.visitIntInsn(SIPUSH, value);
        } else {
            method.visitLdcInsn(value);
        }
    }
}
