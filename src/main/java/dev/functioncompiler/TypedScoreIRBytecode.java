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
 * Direct ASM lowering of IR mutation and scoreboard binary arithmetic.
 * The emitted JVM control-flow jumps across false score predicates; the
 * predicate itself is evaluated at the shared vanilla-compatible runtime
 * boundary, while its accepted terminal mutation is compiled directly.
 *
 * Unlike the old prototype, accepted instructions never call executeStep,
 * ContextChain.runExecutable, ScoreOperationCommand or vanilla Brigadier.
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
    private static final String PREPARED = "dev/functioncompiler/TypedIRPreparedSteps$Prepared";
    private static final String PREPARED_STEPS = "[L" + PREPARED + ";";
    private static final String EXECUTE = "(Ljava/lang/Object;L" + CONTEXT + ";L" + FRAME + ";)V";

    private TypedScoreIRBytecode() {}

    @SuppressWarnings("unchecked")
    static UnboundEntryAction<CommandSourceStack> emit(TypedIROptimizer.Plan optimized) {
        String internal = "dev/functioncompiler/TypedScoreIR$Generated$" + CLASSES.incrementAndGet();
        byte[] bytes = generate(internal, optimized);
        try {
            MethodHandles.Lookup lookup = MethodHandles.lookup().defineHiddenClass(
                    bytes, true, MethodHandles.Lookup.ClassOption.NESTMATE);
            var constructor = lookup.findConstructor(
                    lookup.lookupClass(),
                    MethodType.methodType(void.class, TypedScoreIR.Instruction[].class,
                            TypedIRPreparedSteps.Prepared[].class));
            return (UnboundEntryAction<CommandSourceStack>) constructor.invoke(
                    (Object) optimized.source().instructions().toArray(TypedScoreIR.Instruction[]::new),
                    (Object) TypedIRPreparedSteps.prepare(optimized));
        } catch (Throwable failure) {
            if (failure instanceof Error error) throw error;
            if (failure instanceof RuntimeException runtime) throw runtime;
            throw new IllegalStateException("Typed IR generated class couldn't load", failure);
        }
    }

    private static byte[] generate(String internal, TypedIROptimizer.Plan optimized) {
        ClassWriter writer = new ClassWriter(ClassWriter.COMPUTE_FRAMES | ClassWriter.COMPUTE_MAXS);
        writer.visit(V17, ACC_FINAL | ACC_SUPER, internal, null, "java/lang/Object",
                new String[]{ACTION});
        writer.visitField(ACC_PRIVATE | ACC_FINAL, "steps", STEPS, null, null).visitEnd();
        writer.visitField(ACC_PRIVATE | ACC_FINAL, "prepared", PREPARED_STEPS, null, null).visitEnd();

        MethodVisitor ctor = writer.visitMethod(ACC_PUBLIC, "<init>",
                "(" + STEPS + PREPARED_STEPS + ")V",
                null, null);
        ctor.visitCode();
        ctor.visitVarInsn(ALOAD, 0);
        ctor.visitMethodInsn(INVOKESPECIAL, "java/lang/Object", "<init>", "()V", false);
        ctor.visitVarInsn(ALOAD, 0);
        ctor.visitVarInsn(ALOAD, 1);
        ctor.visitFieldInsn(PUTFIELD, internal, "steps", STEPS);
        ctor.visitVarInsn(ALOAD, 0);
        ctor.visitVarInsn(ALOAD, 2);
        ctor.visitFieldInsn(PUTFIELD, internal, "prepared", PREPARED_STEPS);
        ctor.visitInsn(RETURN);
        ctor.visitMaxs(0, 0);
        ctor.visitEnd();

        MethodVisitor method = writer.visitMethod(ACC_PUBLIC, "execute", EXECUTE, null, null);
        method.visitCode();
        // Local 4: source; 5: invocation state; 6: begin decision;
        // 7: new target score; 8: source score operand;
        // 9: immutable original-instruction vector, loaded once per execution.
        // 10: IR-037 immutable prepared metadata, loaded once per execution.
        //
        // IR-034: the same vector is used by State for reentrant continuation
        // and by every emitted instruction's begin() call. Its final field
        // cannot change during this generated action.
        method.visitVarInsn(ALOAD, 0);
        method.visitFieldInsn(GETFIELD, internal, "steps", STEPS);
        method.visitVarInsn(ASTORE, 9);
        method.visitVarInsn(ALOAD, 0);
        method.visitFieldInsn(GETFIELD, internal, "prepared", PREPARED_STEPS);
        method.visitVarInsn(ASTORE, 10);
        method.visitVarInsn(ALOAD, 1);
        method.visitTypeInsn(CHECKCAST, SOURCE);
        method.visitVarInsn(ASTORE, 4);
        method.visitTypeInsn(NEW, STATE);
        method.visitInsn(DUP);
        method.visitVarInsn(ALOAD, 4);
        method.visitVarInsn(ALOAD, 2);
        method.visitVarInsn(ALOAD, 3);
        method.visitVarInsn(ALOAD, 9);
        method.visitMethodInsn(INVOKESPECIAL, STATE, "<init>",
                "(L" + SOURCE + ";L" + CONTEXT + ";L" + FRAME + ";" + STEPS + ")V", false);
        method.visitVarInsn(ASTORE, 5);
        method.visitMethodInsn(INVOKESTATIC, "dev/functioncompiler/TypedScoreIR",
                "executed", "()V", false);

        Label done = new Label();
        for (int index = 0; index < optimized.steps().size(); index++) {
            TypedIROptimizer.Step step = optimized.steps().get(index);
            Label next = new Label();

            method.visitVarInsn(ALOAD, 5);
            // IR-037: no repeated type/terminal/feedback decoding; original
            // command vectors remain separately available for queue fallback.
            method.visitVarInsn(ALOAD, 10);
            pushInt(method, index);
            method.visitInsn(AALOAD);
            method.visitMethodInsn(INVOKEVIRTUAL, STATE, "begin",
                    "(L" + PREPARED + ";)I", false);
            method.visitVarInsn(ISTORE, 6);

            method.visitVarInsn(ILOAD, 6);
            method.visitJumpInsn(IFEQ, done);
            method.visitVarInsn(ILOAD, 6);
            method.visitInsn(ICONST_2);
            method.visitJumpInsn(IF_ICMPEQ, next);  // original-command fallback
            method.visitVarInsn(ILOAD, 6);
            method.visitInsn(ICONST_3);
            method.visitJumpInsn(IF_ICMPEQ, next);  // conditional branch not taken

            // IR-039: the generated method contains one explicit branch per
            // reached predicate. Known outcomes use a literal, not a score read
            // or a runtime predicate-kind dispatch. Quota is still charged.
            if (step.original() instanceof TypedScoreIR.Compound compound) {
                var stages = CompoundScoreIR.prepare(compound).stages();
                for (int stageIndex = 0; stageIndex < stages.size(); stageIndex++) {
                    var stage = stages.get(stageIndex);
                    method.visitVarInsn(ALOAD, 5);
                    if (stage.evaluation() == CompoundScoreIR.Evaluation.READ) {
                        pushInt(method, stageIndex);
                        method.visitMethodInsn(INVOKEVIRTUAL, STATE, "compoundReadStage", "(I)Z", false);
                    } else {
                        pushInt(method, stageIndex);
                        method.visitInsn(stage.evaluation() == CompoundScoreIR.Evaluation.KNOWN_PASS
                                ? ICONST_1 : ICONST_0);
                        method.visitMethodInsn(INVOKEVIRTUAL, STATE, "compoundKnownStage", "(IZ)Z", false);
                    }
                    method.visitJumpInsn(IFEQ, next);
                }
                method.visitVarInsn(ALOAD, 5);
                method.visitMethodInsn(INVOKEVIRTUAL, STATE, "compoundTerminal", "()Z", false);
                method.visitJumpInsn(IFEQ, next);
            }

            // IR-035: no per-command lowering/type inspection in the backend.
            // These preclassified opcodes never merge original source entries.
            if (step.opcode() == TypedIROptimizer.Op.DIVIDE_SCORE
                    || step.opcode() == TypedIROptimizer.Op.MODULO_SCORE
                    || step.opcode() == TypedIROptimizer.Op.SWAP_SCORE) {
                method.visitVarInsn(ALOAD, 5);
                method.visitMethodInsn(INVOKEVIRTUAL, STATE, "applyNativeArithmetic", "()V", false);
                method.visitJumpInsn(GOTO, next);
            } else if (step.opcode().readsSourceScore()) {
                emitBinary(method, step);
            } else {
                emitMutation(method, step);
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

    private static void target(MethodVisitor method) {
        method.visitVarInsn(ALOAD, 5);
        method.visitMethodInsn(INVOKEVIRTUAL, STATE, "access",
                "()L" + SCORE + ";", false);
    }

    private static void emitMutation(MethodVisitor method, TypedIROptimizer.Step step) {
        target(method);
        switch (step.opcode()) {
            case ADD_LITERAL -> {
                // IR-035 canonicalizes original ADD and REMOVE to a signed
                // 32-bit delta. The original action still determines feedback.
                pushInt(method, step.literal());
                method.visitMethodInsn(INVOKEINTERFACE, SCORE, "add", "(I)I", true);
                method.visitVarInsn(ISTORE, 7);
            }
            case SET_LITERAL -> {
                pushInt(method, step.literal());
                method.visitMethodInsn(INVOKEINTERFACE, SCORE, "set", "(I)V", true);
                pushInt(method, step.literal());
                method.visitVarInsn(ISTORE, 7);
            }
            default -> throw new IllegalArgumentException("binary opcode in literal emitter");
        }
    }

    private static void emitBinary(MethodVisitor method, TypedIROptimizer.Step step) {
        method.visitVarInsn(ALOAD, 5);
        method.visitMethodInsn(INVOKEVIRTUAL, STATE, "sourceAccess",
                "()L" + SCORE + ";", false);
        method.visitMethodInsn(INVOKEINTERFACE, SCORE, "get", "()I", true);
        method.visitVarInsn(ISTORE, 8);

        target(method);
        method.visitVarInsn(ILOAD, 8);
        switch (step.opcode()) {
            case ASSIGN_SCORE -> {
                method.visitMethodInsn(INVOKEINTERFACE, SCORE, "set", "(I)V", true);
                method.visitVarInsn(ILOAD, 8);
                method.visitVarInsn(ISTORE, 7);
            }
            case ADD_SCORE, SUBTRACT_SCORE -> {
                if (step.opcode() == TypedIROptimizer.Op.SUBTRACT_SCORE) {
                    method.visitInsn(INEG);
                }
                method.visitMethodInsn(INVOKEINTERFACE, SCORE, "add", "(I)I", true);
                method.visitVarInsn(ISTORE, 7);
            }
            case MIN_SCORE, MAX_SCORE -> {
                method.visitInsn(POP);
                method.visitInsn(DUP);
                method.visitMethodInsn(INVOKEINTERFACE, SCORE, "get", "()I", true);
                method.visitVarInsn(ILOAD, 8);
                method.visitMethodInsn(INVOKESTATIC, "java/lang/Math",
                        step.opcode() == TypedIROptimizer.Op.MIN_SCORE ? "min" : "max",
                        "(II)I", false);
                method.visitInsn(DUP);
                method.visitVarInsn(ISTORE, 7);
                method.visitMethodInsn(INVOKEINTERFACE, SCORE, "set", "(I)V", true);
            }
            case MULTIPLY_SCORE -> {
                // Retain original source-before-target read sequencing.
                method.visitInsn(POP);
                method.visitInsn(DUP);
                method.visitMethodInsn(INVOKEINTERFACE, SCORE, "get", "()I", true);
                method.visitVarInsn(ILOAD, 8);
                method.visitInsn(IMUL);
                method.visitInsn(DUP);
                method.visitVarInsn(ISTORE, 7);
                method.visitMethodInsn(INVOKEINTERFACE, SCORE, "set", "(I)V", true);
            }
            default -> throw new IllegalArgumentException("literal opcode in score emitter");
        }
    }

    private static void pushInt(MethodVisitor method, int value) {
        if (value >= -1 && value <= 5) method.visitInsn(ICONST_0 + value);
        else if (value >= Byte.MIN_VALUE && value <= Byte.MAX_VALUE) method.visitIntInsn(BIPUSH, value);
        else if (value >= Short.MIN_VALUE && value <= Short.MAX_VALUE) method.visitIntInsn(SIPUSH, value);
        else method.visitLdcInsn(value);
    }
}
