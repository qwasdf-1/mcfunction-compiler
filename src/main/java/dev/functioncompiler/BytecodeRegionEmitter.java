package dev.functioncompiler;

import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.Label;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

final class BytecodeRegionEmitter {
    static final int STEPS_PER_METHOD = 256;
    private static final String ACTION_INTERNAL_NAME =
            "net/minecraft/commands/execution/UnboundEntryAction";
    private static final String SOURCE_INTERNAL_NAME =
            "net/minecraft/commands/CommandSourceStack";
    private static final String EXECUTION_CONTEXT_INTERNAL_NAME =
            "net/minecraft/commands/execution/ExecutionContext";
    private static final String FRAME_INTERNAL_NAME =
            "net/minecraft/commands/execution/Frame";
    private static final String COMMANDS_FIELD_DESCRIPTOR = "[Ljava/lang/Object;";
    private static final String EXECUTE_DESCRIPTOR =
            "(Ljava/lang/Object;L" + EXECUTION_CONTEXT_INTERNAL_NAME
                    + ";L" + FRAME_INTERNAL_NAME + ";)V";
    private static final String EXECUTE_STEP_DESCRIPTOR =
            "([Ljava/lang/Object;IL" + SOURCE_INTERNAL_NAME + ";L"
                    + EXECUTION_CONTEXT_INTERNAL_NAME + ";L" + FRAME_INTERNAL_NAME + ";)Z";
    private static final String BLOCK_DESCRIPTOR =
            "(L" + SOURCE_INTERNAL_NAME + ";L" + EXECUTION_CONTEXT_INTERNAL_NAME
                    + ";L" + FRAME_INTERNAL_NAME + ";)Z";

    private BytecodeRegionEmitter() {
    }

    static byte[] emitClass(String internalName, int commandCount) {
        ClassWriter writer = new ClassWriter(ClassWriter.COMPUTE_FRAMES | ClassWriter.COMPUTE_MAXS);
        writer.visit(
                Opcodes.V17,
                Opcodes.ACC_FINAL | Opcodes.ACC_SUPER,
                internalName,
                null,
                "java/lang/Object",
                new String[]{ACTION_INTERNAL_NAME}
        );
        writer.visitField(
                Opcodes.ACC_PRIVATE | Opcodes.ACC_FINAL,
                "commands",
                COMMANDS_FIELD_DESCRIPTOR,
                null,
                null
        ).visitEnd();
        emitConstructor(writer, internalName);

        int blockCount = (commandCount + STEPS_PER_METHOD - 1) / STEPS_PER_METHOD;
        for (int block = 0; block < blockCount; block++) {
            emitBlock(writer, internalName, block, commandCount);
        }
        emitExecute(writer, internalName, blockCount);
        writer.visitEnd();
        return writer.toByteArray();
    }

    private static void emitConstructor(ClassWriter writer, String internalName) {
        MethodVisitor method = writer.visitMethod(
                Opcodes.ACC_PUBLIC,
                "<init>",
                "([Ljava/lang/Object;)V",
                null,
                null
        );
        method.visitCode();
        method.visitVarInsn(Opcodes.ALOAD, 0);
        method.visitMethodInsn(
                Opcodes.INVOKESPECIAL,
                "java/lang/Object",
                "<init>",
                "()V",
                false
        );
        method.visitVarInsn(Opcodes.ALOAD, 0);
        method.visitVarInsn(Opcodes.ALOAD, 1);
        method.visitFieldInsn(
                Opcodes.PUTFIELD,
                internalName,
                "commands",
                COMMANDS_FIELD_DESCRIPTOR
        );
        method.visitInsn(Opcodes.RETURN);
        method.visitMaxs(0, 0);
        method.visitEnd();
    }

    private static void emitBlock(
            ClassWriter writer,
            String internalName,
            int block,
            int commandCount
    ) {
        String methodName = "executeBlock$" + block;
        MethodVisitor method = writer.visitMethod(
                Opcodes.ACC_PRIVATE,
                methodName,
                BLOCK_DESCRIPTOR,
                null,
                null
        );
        method.visitCode();

        int start = block * STEPS_PER_METHOD;
        int end = Math.min(start + STEPS_PER_METHOD, commandCount);
        for (int index = start; index < end; index++) {
            Label nextStep = new Label();
            method.visitVarInsn(Opcodes.ALOAD, 0);
            method.visitFieldInsn(
                Opcodes.GETFIELD,
                internalName,
                "commands",
                COMMANDS_FIELD_DESCRIPTOR
            );
            pushInt(method, index);
            method.visitVarInsn(Opcodes.ALOAD, 1);
            method.visitVarInsn(Opcodes.ALOAD, 2);
            method.visitVarInsn(Opcodes.ALOAD, 3);
            method.visitMethodInsn(
                    Opcodes.INVOKESTATIC,
                    "dev/functioncompiler/BytecodeRegionPrototype",
                    "executeStep",
                    EXECUTE_STEP_DESCRIPTOR,
                    false
            );
            method.visitJumpInsn(Opcodes.IFNE, nextStep);
            method.visitInsn(Opcodes.ICONST_0);
            method.visitInsn(Opcodes.IRETURN);
            method.visitLabel(nextStep);
        }
        method.visitInsn(Opcodes.ICONST_1);
        method.visitInsn(Opcodes.IRETURN);

        method.visitMaxs(0, 0);
        method.visitEnd();
    }

    private static void emitExecute(ClassWriter writer, String internalName, int blockCount) {
        MethodVisitor method = writer.visitMethod(
                Opcodes.ACC_PUBLIC,
                "execute",
                EXECUTE_DESCRIPTOR,
                null,
                null
        );
        method.visitCode();
        Label done = new Label();
        method.visitMethodInsn(
                Opcodes.INVOKESTATIC,
                "dev/functioncompiler/BytecodeRegionPrototype",
                "beginExecution",
                "()V",
                false
        );
        method.visitVarInsn(Opcodes.ALOAD, 1);
        method.visitTypeInsn(Opcodes.CHECKCAST, SOURCE_INTERNAL_NAME);
        method.visitVarInsn(Opcodes.ASTORE, 4);

        for (int block = 0; block < blockCount; block++) {
            method.visitVarInsn(Opcodes.ALOAD, 0);
            method.visitVarInsn(Opcodes.ALOAD, 4);
            method.visitVarInsn(Opcodes.ALOAD, 2);
            method.visitVarInsn(Opcodes.ALOAD, 3);
            method.visitMethodInsn(
                    Opcodes.INVOKESPECIAL,
                    internalName,
                    "executeBlock$" + block,
                    BLOCK_DESCRIPTOR,
                    false
            );
            method.visitJumpInsn(Opcodes.IFEQ, done);
        }
        method.visitLabel(done);
        method.visitInsn(Opcodes.RETURN);
        method.visitMaxs(0, 0);
        method.visitEnd();
    }

    private static void pushInt(MethodVisitor method, int value) {
        if (value >= -1 && value <= 5) {
            method.visitInsn(Opcodes.ICONST_0 + value);
        } else if (value <= Byte.MAX_VALUE) {
            method.visitIntInsn(Opcodes.BIPUSH, value);
        } else if (value <= Short.MAX_VALUE) {
            method.visitIntInsn(Opcodes.SIPUSH, value);
        } else {
            method.visitLdcInsn(value);
        }
    }
}
