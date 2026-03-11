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
