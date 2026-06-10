from django.db.models import Max
from rest_framework import serializers

from .models import ItemRelation, RelationType


class RelationTypeSerializer(serializers.ModelSerializer):
    source_item_type_name = serializers.CharField(
        source="source_item_type.name", read_only=True, default=None
    )
    target_item_type_name = serializers.CharField(
        source="target_item_type.name", read_only=True, default=None
    )

    class Meta:
        model = RelationType
        fields = [
            "id",
            "kind",
            "name",
            "forward_label",
            "reverse_label",
            "description",
            "source_item_type",
            "source_item_type_name",
            "target_item_type",
            "target_item_type_name",
            "is_builtin",
            "is_active",
        ]
        read_only_fields = ["id", "is_builtin"]

    def validate_name(self, value):
        vault = self.instance.vault if self.instance else self.context["request"].user.active_vault
        qs = RelationType.objects.filter(vault=vault, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A relation type with this name already exists in this vault."
            )
        return value

    def create(self, validated_data):
        validated_data["vault"] = self.context["request"].user.active_vault
        return super().create(validated_data)


class ItemRelationSerializer(serializers.ModelSerializer):
    relation_type_name = serializers.CharField(
        source="relation_type.name", read_only=True
    )
    forward_label = serializers.CharField(
        source="relation_type.forward_label", read_only=True
    )
    reverse_label = serializers.CharField(
        source="relation_type.reverse_label", read_only=True
    )
    source_title = serializers.CharField(source="source.title", read_only=True)
    target_title = serializers.CharField(source="target.title", read_only=True)
    source_type_slug = serializers.CharField(
        source="source.item_type.slug", read_only=True
    )
    target_type_slug = serializers.CharField(
        source="target.item_type.slug", read_only=True
    )

    class Meta:
        model = ItemRelation
        fields = [
            "id",
            "relation_type",
            "relation_type_name",
            "forward_label",
            "reverse_label",
            "source",
            "source_title",
            "source_type_slug",
            "source_version",
            "target",
            "target_title",
            "target_type_slug",
            "target_version",
            "version_pinned",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "source_version", "target_version", "version_pinned", "created_by", "created_at"]

    def validate(self, data):
        rt = data.get("relation_type")
        source = data.get("source")
        target = data.get("target")

        # Enforce vault isolation: relation_type and both items must belong to
        # the caller's active vault. Without this, a user could link or relate
        # items across vaults by passing foreign UUIDs.
        request = self.context.get("request")
        vault = getattr(getattr(request, "user", None), "active_vault", None)
        if vault is None:
            raise serializers.ValidationError("No active vault selected.")
        if rt and rt.vault_id != vault.id:
            raise serializers.ValidationError(
                {"relation_type": "Relation type does not belong to the active vault."}
            )
        if source and source.item_type.vault_id != vault.id:
            raise serializers.ValidationError(
                {"source": "Source item does not belong to the active vault."}
            )
        if target and target.item_type.vault_id != vault.id:
            raise serializers.ValidationError(
                {"target": "Target item does not belong to the active vault."}
            )

        if source and target and source == target:
            raise serializers.ValidationError("An item cannot relate to itself.")
        if rt and source and rt.source_item_type_id:
            if source.item_type_id != rt.source_item_type_id:
                raise serializers.ValidationError(
                    {"source": f"Source item must be of type '{rt.source_item_type.name}'."}
                )
        if rt and target and rt.target_item_type_id:
            if target.item_type_id != rt.target_item_type_id:
                raise serializers.ValidationError(
                    {"target": f"Target item must be of type '{rt.target_item_type.name}'."}
                )
        if rt and source and target:
            qs = ItemRelation.objects.filter(
                relation_type=rt, source=source, target=target,
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "This relation already exists."
                )
        return data

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        # Auto-set versions to current for suspect-link tracking
        source = validated_data["source"]
        target = validated_data["target"]
        validated_data["source_version"] = source.current_version
        validated_data["target_version"] = target.current_version
        rt = validated_data.get("relation_type")
        if rt and rt.kind == RelationType.Kind.COMPOSITION:
            max_pos = (
                ItemRelation.objects.filter(
                    source=validated_data["source"],
                    relation_type__kind=RelationType.Kind.COMPOSITION,
                )
                .aggregate(max_pos=Max("position"))["max_pos"]
            )
            validated_data["position"] = (max_pos or 0) + 10
        return super().create(validated_data)
