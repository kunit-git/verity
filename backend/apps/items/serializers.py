from django.db import transaction

from rest_framework import serializers

from .models import CustomFieldDefinition, CustomFieldValue, Item, ItemType, ItemVersion


class CustomFieldDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomFieldDefinition
        fields = [
            "id",
            "name",
            "slug",
            "field_kind",
            "is_required",
            "options",
            "display_order",
        ]


class ItemTypeSerializer(serializers.ModelSerializer):
    custom_fields = CustomFieldDefinitionSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ItemType
        fields = ["id", "name", "slug", "description", "icon", "is_active", "custom_fields", "item_count"]
        read_only_fields = ["id"]


class ItemTypeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemType
        fields = ["id", "name", "slug", "description", "icon"]
        read_only_fields = ["id"]


class ItemVersionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = ItemVersion
        fields = [
            "id",
            "version_number",
            "title",
            "description",
            "status",
            "custom_fields_snapshot",
            "created_by",
            "created_by_username",
            "created_at",
            "change_summary",
        ]
        read_only_fields = fields


class TreeNodeSerializer(serializers.ModelSerializer):
    item_type_slug = serializers.CharField(source="item_type.slug", read_only=True)
    child_count = serializers.IntegerField(read_only=True)
    position = serializers.IntegerField(source="rel_position", read_only=True, default=0)
    has_suspect_links = serializers.BooleanField(read_only=True, default=False)
    has_suspect_descendants = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Item
        fields = ["id", "title", "item_type_slug", "child_count", "position", "has_suspect_links", "has_suspect_descendants"]


class ItemListSerializer(serializers.ModelSerializer):
    item_type_name = serializers.CharField(source="item_type.name", read_only=True)
    item_type_slug = serializers.CharField(source="item_type.slug", read_only=True)
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = Item
        fields = [
            "id",
            "title",
            "status",
            "item_type",
            "item_type_name",
            "item_type_slug",
            "created_by",
            "created_by_username",
            "current_version",
            "created_at",
            "updated_at",
        ]


class ItemSerializer(serializers.ModelSerializer):
    item_type_name = serializers.CharField(source="item_type.name", read_only=True)
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    custom_fields = serializers.DictField(required=False, default=dict)

    class Meta:
        model = Item
        fields = [
            "id",
            "title",
            "description",
            "status",
            "item_type",
            "item_type_name",
            "created_by",
            "created_by_username",
            "custom_fields",
            "current_version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "current_version", "created_at", "updated_at"]

    def _validate_custom_fields(self, item_type, custom_fields_data):
        field_defs = {
            fd.slug: fd
            for fd in CustomFieldDefinition.objects.filter(item_type=item_type)
        }

        # Check required fields
        for slug, fd in field_defs.items():
            if fd.is_required and slug not in custom_fields_data:
                raise serializers.ValidationError(
                    {"custom_fields": {slug: "This field is required."}}
                )

        # Check for unknown fields
        for slug in custom_fields_data:
            if slug not in field_defs:
                raise serializers.ValidationError(
                    {"custom_fields": {slug: f"Unknown field for this item type."}}
                )

        return field_defs

    def create(self, validated_data):
        custom_fields_data = validated_data.pop("custom_fields", {})
        validated_data["created_by"] = self.context["request"].user
        item_type = validated_data["item_type"]

        field_defs = self._validate_custom_fields(item_type, custom_fields_data)

        item = Item.objects.create(**validated_data)

        for slug, value in custom_fields_data.items():
            CustomFieldValue.objects.create(
                item=item, field_definition=field_defs[slug], value=value
            )

        return item

    def update(self, instance, validated_data):
        custom_fields_data = validated_data.pop("custom_fields", None)

        with transaction.atomic():
            # Snapshot current state before applying changes
            current_cfv = {
                cfv.field_definition.slug: cfv.value
                for cfv in instance.custom_field_values.select_related("field_definition")
            }
            # Lock the item row to prevent concurrent version races
            Item.objects.select_for_update().filter(pk=instance.pk).first()

            ItemVersion.objects.create(
                item=instance,
                version_number=instance.current_version,
                title=instance.title,
                description=instance.description,
                status=instance.status,
                custom_fields_snapshot=current_cfv,
                created_by=self.context["request"].user,
                change_summary=self.context["request"].data.get("change_summary", ""),
            )

            instance.current_version += 1

            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if custom_fields_data is not None:
                field_defs = self._validate_custom_fields(
                    instance.item_type, custom_fields_data
                )
                for slug, value in custom_fields_data.items():
                    CustomFieldValue.objects.update_or_create(
                        item=instance,
                        field_definition=field_defs[slug],
                        defaults={"value": value},
                    )

        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Replace custom_fields dict with actual values from DB
        cfv_qs = instance.custom_field_values.select_related("field_definition")
        data["custom_fields"] = {
            cfv.field_definition.slug: cfv.value for cfv in cfv_qs
        }
        return data
