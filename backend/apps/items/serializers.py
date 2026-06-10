from django.db import transaction
from django.db.models import Q

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

    def validate_slug(self, value):
        item_type = self.context.get("item_type")
        if self.instance:
            item_type = self.instance.item_type
        if item_type:
            qs = CustomFieldDefinition.objects.filter(
                item_type=item_type, slug=value,
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "A custom field with this slug already exists for this item type."
                )
        return value

    def validate(self, data):
        field_kind = data.get("field_kind", getattr(self.instance, "field_kind", None))
        options = data.get("options", getattr(self.instance, "options", {}))
        if field_kind == CustomFieldDefinition.FieldKind.TABLE:
            self._validate_table_schema(options)
        return data

    def _validate_table_schema(self, options):
        from apps.matrices.formula import validate_formula, parse_formula, extract_references, ParseError

        columns = options.get("columns") if options else None
        if not isinstance(columns, list) or len(columns) == 0:
            raise serializers.ValidationError(
                {"options": "Table fields must have at least one column in options.columns."}
            )

        names = set()
        annotation_slugs = set()
        for i, col in enumerate(columns):
            # Validate name
            name = col.get("name", "")
            if not name:
                raise serializers.ValidationError(
                    {"options": f"Column {i}: name is required."}
                )
            if name in names:
                raise serializers.ValidationError(
                    {"options": f"Column {i}: name '{name}' is not unique within this table."}
                )
            names.add(name)

            kind = col.get("kind")
            if kind not in ("traversal", "item_field", "annotation", "formula"):
                raise serializers.ValidationError(
                    {"options": f"Column {i}: invalid kind '{kind}'. Must be traversal, item_field, annotation, or formula."}
                )
            if i == 0 and kind != "traversal":
                raise serializers.ValidationError(
                    {"options": "The first column of a table field must be a traversal column."}
                )
            if kind == "traversal":
                if not col.get("relation_type_id"):
                    raise serializers.ValidationError(
                        {"options": f"Column {i}: traversal columns require relation_type_id."}
                    )
                if col.get("direction") not in ("outgoing", "incoming"):
                    raise serializers.ValidationError(
                        {"options": f"Column {i}: traversal columns require direction ('outgoing' or 'incoming')."}
                    )
            elif kind == "annotation":
                slug = col.get("slug", "")
                if not slug:
                    raise serializers.ValidationError(
                        {"options": f"Column {i}: annotation columns require a slug."}
                    )
                if slug in annotation_slugs:
                    raise serializers.ValidationError(
                        {"options": f"Column {i}: annotation slug '{slug}' is not unique within this table."}
                    )
                annotation_slugs.add(slug)
            elif kind == "item_field":
                if not col.get("field_slug"):
                    raise serializers.ValidationError(
                        {"options": f"Column {i}: item_field columns require field_slug."}
                    )
                source_ref = col.get("source_ref", "")
                if not source_ref:
                    raise serializers.ValidationError(
                        {"options": f"Column {i}: item_field columns require source_ref."}
                    )
                if source_ref not in names:
                    raise serializers.ValidationError(
                        {"options": f"Column {i}: source_ref '{source_ref}' references unknown column."}
                    )
            elif kind == "formula":
                formula = col.get("formula", "")
                if not formula:
                    raise serializers.ValidationError(
                        {"options": f"Column {i}: formula columns require a formula."}
                    )
                errors = validate_formula(formula)
                if errors:
                    raise serializers.ValidationError(
                        {"options": f"Column {i}: invalid formula: {errors[0]}"}
                    )
                # Validate formula references exist
                try:
                    ast = parse_formula(formula)
                    refs = extract_references(ast)
                    for ref_name, _ in refs:
                        if ref_name not in names:
                            raise serializers.ValidationError(
                                {"options": f"Column {i}: formula references unknown source '{ref_name}'."}
                            )
                except ParseError:
                    pass  # Already caught above


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

    def _get_vault(self):
        if self.instance:
            return self.instance.vault
        return self.context["request"].user.active_vault

    def validate_name(self, value):
        vault = self._get_vault()
        qs = ItemType.objects.filter(vault=vault, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "An item type with this name already exists in this vault."
            )
        return value

    def validate_slug(self, value):
        vault = self._get_vault()
        qs = ItemType.objects.filter(vault=vault, slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "An item type with this slug already exists in this vault."
            )
        return value

    def create(self, validated_data):
        validated_data["vault"] = self.context["request"].user.active_vault
        return super().create(validated_data)


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

    def validate_item_type(self, value):
        request = self.context.get("request")
        vault = getattr(getattr(request, "user", None), "active_vault", None)
        if vault is None or value.vault_id != vault.id:
            raise serializers.ValidationError(
                "Item type does not belong to the active vault."
            )
        return value

    def _validate_custom_fields(self, item_type, custom_fields_data):
        field_defs = {
            fd.slug: fd
            for fd in CustomFieldDefinition.objects.filter(item_type=item_type)
            # Table fields have no CustomFieldValue rows — exclude from validation
            if fd.field_kind != CustomFieldDefinition.FieldKind.TABLE
        }

        # Check required fields (table fields are never required via custom_fields)
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
                for cfv in CustomFieldValue.objects.filter(item=instance).select_related("field_definition")
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

            # Reset version_pinned on all relations involving this item
            # so pinned relations become suspect again for new unreviewed changes
            from apps.relations.models import ItemRelation
            ItemRelation.objects.filter(
                Q(source=instance) | Q(target=instance),
                version_pinned=True,
            ).update(version_pinned=False)

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
        # Table fields are excluded — their data is served via the table-field data endpoint
        cfv_qs = (
            CustomFieldValue.objects.filter(item=instance)
            .select_related("field_definition")
            .exclude(field_definition__field_kind=CustomFieldDefinition.FieldKind.TABLE)
        )
        data["custom_fields"] = {
            cfv.field_definition.slug: cfv.value for cfv in cfv_qs
        }
        return data
