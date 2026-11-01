package dev.functioncompiler;

import net.minecraft.world.entity.Attackable;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Leashable;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.OwnableEntity;
import net.minecraft.world.entity.Targeting;
import net.minecraft.world.entity.TraceableEntity;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

enum EntityRelation {
    OWNER {
        @Override
        List<? extends Entity> resolve(Entity entity) {
            if (entity instanceof OwnableEntity ownable) {
                LivingEntity owner = ownable.getOwner();
                if (owner != null && !owner.isRemoved()) {
                    return List.of(owner);
                }
            }
            return List.of();
        }
    },
    LEASHER {
        @Override
        List<? extends Entity> resolve(Entity entity) {
            if (entity instanceof Leashable leashable) {
                Entity holder = leashable.getLeashHolder();
                if (holder != null && !holder.isRemoved()) {
                    return List.of(holder);
                }
            }
            return List.of();
        }
    },
    TARGET {
        @Override
        List<? extends Entity> resolve(Entity entity) {
            if (entity instanceof Targeting targeting) {
                LivingEntity target = targeting.getTarget();
                if (target != null && !target.isRemoved()) {
                    return List.of(target);
                }
            }
            return List.of();
        }
    },
    ATTACKER {
        @Override
        List<? extends Entity> resolve(Entity entity) {
            if (entity instanceof Attackable attackable) {
                LivingEntity attacker = attackable.getLastAttacker();
                if (attacker != null && !attacker.isRemoved()) {
                    return List.of(attacker);
                }
            }
            return List.of();
        }
    },
    VEHICLE {
        @Override
        List<? extends Entity> resolve(Entity entity) {
            Entity vehicle = entity.getVehicle();
            return (vehicle != null && !vehicle.isRemoved()) ? List.of(vehicle) : List.of();
        }
    },
    CONTROLLER {
        @Override
        List<? extends Entity> resolve(Entity entity) {
            LivingEntity controller = entity.getControllingPassenger();
            return (controller != null && !controller.isRemoved()) ? List.of(controller) : List.of();
        }
    },
    ORIGIN {
        @Override
        List<? extends Entity> resolve(Entity entity) {
            if (entity instanceof TraceableEntity traceable) {
                Entity origin = traceable.getOwner();
                if (origin != null && !origin.isRemoved()) {
                    return List.of(origin);
                }
            }
            return List.of();
        }
    },
    PASSENGERS {
        @Override
        List<? extends Entity> resolve(Entity entity) {
            List<Entity> passengers = entity.getPassengers();
            if (passengers.isEmpty()) {
                return List.of();
            }
            List<Entity> active = new ArrayList<>(passengers.size());
            for (Entity passenger : passengers) {
                if (!passenger.isRemoved()) {
                    active.add(passenger);
                }
            }
            return active;
        }
    };

    private static final Map<String, EntityRelation> BY_NAME = Map.of(
            "owner", OWNER,
            "leasher", LEASHER,
            "target", TARGET,
            "attacker", ATTACKER,
            "vehicle", VEHICLE,
            "controller", CONTROLLER,
            "origin", ORIGIN,
            "passengers", PASSENGERS
    );

    static EntityRelation fromName(String name) {
        return BY_NAME.get(name);
    }

    abstract List<? extends Entity> resolve(Entity entity);
}
