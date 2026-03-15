from rest_framework import serializers

from .formula import validate_formula
from .models import Matrix, MatrixDisplayColumn, MatrixSource


class MatrixSourceSerializer(serializers.ModelSerializer):
    seed_item_type_name = serializers.CharField(
        source="seed_item_type.name", read_only=True, default=None
    )
    seed_container_title = serializers.CharField(
        source="seed_container.title", read_only=True, default=None
    )
    relation_type_name = serializers.CharField(
        source="relation_type.name", read_only=True, default=None
    )
    relation_forward_label = serializers.CharField(
        source="relation_type.forward_label", read_only=True, default=None
    )
    relation_reverse_label = serializers.CharField(
        source="relation_type.reverse_label", read_only=True, default=None
    )

    class Meta:
        model = MatrixSource
        fields = [
            "id",
            "name",
            "position",
            "kind",
            "seed_item_type",
            "seed_item_type_name",
            "seed_container",
            "seed_container_title",
            "relation_type",
            "relation_type_name",
            "relation_forward_label",
            "relation_reverse_label",
            "direction",
            "formula",
            "source_ref",
            "field_slug",
        ]
        read_only_fields = ["id"]


class MatrixSourceWriteSerializer(serializers.Serializer):
    name = serializers.SlugField(max_length=100)
    kind = serializers.ChoiceField(choices=MatrixSource.Kind.choices)
    seed_item_type = serializers.UUIDField(required=False, allow_null=True)
    seed_container = serializers.UUIDField(required=False, allow_null=True)
    relation_type = serializers.UUIDField(required=False, allow_null=True)
    direction = serializers.ChoiceField(
        choices=MatrixSource.Direction.choices, required=False, allow_null=True
    )
    formula = serializers.CharField(required=False, allow_blank=True, default="")
    source_ref = serializers.SlugField(required=False, allow_blank=True, default="")
    field_slug = serializers.SlugField(required=False, allow_blank=True, default="")

    def validate(self, data):
        kind = data.get("kind")
        seed_item_type = data.get("seed_item_type")
        relation_type = data.get("relation_type")
        direction = data.get("direction")
        formula = data.get("formula", "")
        source_ref = data.get("source_ref", "")
        field_slug = data.get("field_slug", "")

        if kind == "seed":
            if not seed_item_type:
                raise serializers.ValidationError(
                    "Seed sources must specify seed_item_type."
                )
            if relation_type or direction:
                raise serializers.ValidationError(
                    "Seed sources must not specify relation_type or direction."
                )
            if formula:
                raise serializers.ValidationError(
                    "Seed sources must not have a formula."
                )
        elif kind == "traversal":
            if not relation_type:
                raise serializers.ValidationError(
                    "Traversal sources must specify relation_type."
                )
            if not direction:
                raise serializers.ValidationError(
                    "Traversal sources must specify direction."
                )
            if formula:
                raise serializers.ValidationError(
                    "Traversal sources must not have a formula."
                )
        elif kind == "formula":
            if not formula:
                raise serializers.ValidationError(
                    "Formula sources must specify a formula."
                )
            if relation_type or direction:
                raise serializers.ValidationError(
                    "Formula sources must not specify relation_type or direction."
                )
            errors = validate_formula(formula)
            if errors:
                raise serializers.ValidationError(
                    f"Invalid formula: {errors[0]}"
                )
        elif kind == "annotation":
            if relation_type or direction or formula:
                raise serializers.ValidationError(
                    "Annotation sources must not specify relation_type, direction, or formula."
                )
        elif kind == "item_field":
            if not field_slug:
                raise serializers.ValidationError(
                    "Item field sources must specify field_slug."
                )
            if not source_ref:
                raise serializers.ValidationError(
                    "Item field sources must specify source_ref."
                )
            if relation_type or direction or formula:
                raise serializers.ValidationError(
                    "Item field sources must not specify relation_type, direction, or formula."
                )
        else:
            raise serializers.ValidationError(f"Invalid kind: {kind}")

        return data


class MatrixDisplayColumnWriteSerializer(serializers.Serializer):
    heading = serializers.CharField(max_length=200)
    source = serializers.SlugField(max_length=100)


class MatrixDisplayColumnSerializer(serializers.ModelSerializer):
    source = serializers.CharField(source="source_name")

    class Meta:
        model = MatrixDisplayColumn
        fields = ["id", "position", "heading", "source"]
        read_only_fields = ["id"]


class MatrixSerializer(serializers.ModelSerializer):
    sources = serializers.SerializerMethodField()
    columns = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = Matrix
        fields = [
            "id",
            "name",
            "description",
            "created_by",
            "created_by_username",
            "sources",
            "columns",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def get_sources(self, obj):
        sources = MatrixSource.objects.filter(matrix=obj).select_related(
            "seed_item_type", "seed_container", "relation_type"
        )
        return MatrixSourceSerializer(sources, many=True).data

    def get_columns(self, obj):
        columns = MatrixDisplayColumn.objects.filter(matrix=obj)
        return MatrixDisplayColumnSerializer(columns, many=True).data


class MatrixWriteSerializer(serializers.ModelSerializer):
    sources = MatrixSourceWriteSerializer(many=True)
    columns = MatrixDisplayColumnWriteSerializer(many=True)

    class Meta:
        model = Matrix
        fields = ["id", "name", "description", "sources", "columns"]
        read_only_fields = ["id"]

    def validate(self, data):
        sources = data.get("sources", [])
        columns = data.get("columns", [])

        if not sources:
            raise serializers.ValidationError(
                {"sources": "At least one source is required."}
            )

        # First source must be seed
        if sources[0].get("kind") != "seed":
            raise serializers.ValidationError(
                {"sources": "First source must be a seed."}
            )

        # Source names must be unique
        names = [s["name"] for s in sources]
        if len(names) != len(set(names)):
            raise serializers.ValidationError(
                {"sources": "Source names must be unique."}
            )

        name_set = set(names)

        # Validate formula references and item_field source_ref
        from .formula import extract_references, parse_formula, ParseError

        for src in sources:
            if src.get("kind") == "formula" and src.get("formula"):
                try:
                    ast = parse_formula(src["formula"])
                    refs = extract_references(ast)
                    for ref_name, _ in refs:
                        if ref_name not in name_set:
                            raise serializers.ValidationError(
                                {"sources": f"Formula in '{src['name']}' references unknown source '{ref_name}'."}
                            )
                except ParseError:
                    pass  # Syntax error already caught by source serializer

            if src.get("kind") == "item_field" and src.get("source_ref"):
                if src["source_ref"] not in name_set:
                    raise serializers.ValidationError(
                        {"sources": f"Item field '{src['name']}' references unknown source '{src['source_ref']}'."}
                    )

        # Validate display column source references
        for col in columns:
            if col["source"] not in name_set:
                raise serializers.ValidationError(
                    {"columns": f"Column '{col['heading']}' references unknown source '{col['source']}'."}
                )

        return data

    def _resolve_fks(self, source_data):
        """Resolve UUID fields to FK objects for MatrixSource creation."""
        from apps.items.models import Item, ItemType
        from apps.relations.models import RelationType

        result = dict(source_data)

        seed_item_type = result.pop("seed_item_type", None)
        if seed_item_type:
            result["seed_item_type"] = ItemType.objects.get(id=seed_item_type)
        else:
            result["seed_item_type"] = None

        seed_container = result.pop("seed_container", None)
        if seed_container:
            result["seed_container"] = Item.objects.get(id=seed_container)
        else:
            result["seed_container"] = None

        relation_type = result.pop("relation_type", None)
        if relation_type:
            result["relation_type"] = RelationType.objects.get(id=relation_type)
        else:
            result["relation_type"] = None

        return result

    def create(self, validated_data):
        sources_data = validated_data.pop("sources")
        columns_data = validated_data.pop("columns")
        validated_data["created_by"] = self.context["request"].user
        validated_data["vault"] = self.context["request"].user.active_vault
        matrix = Matrix.objects.create(**validated_data)

        for position, src_data in enumerate(sources_data):
            resolved = self._resolve_fks(src_data)
            MatrixSource.objects.create(matrix=matrix, position=position, **resolved)

        for position, col_data in enumerate(columns_data):
            MatrixDisplayColumn.objects.create(
                matrix=matrix,
                position=position,
                heading=col_data["heading"],
                source_name=col_data["source"],
            )

        return matrix

    def update(self, instance, validated_data):
        sources_data = validated_data.pop("sources", None)
        columns_data = validated_data.pop("columns", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if sources_data is not None:
            instance.sources.all().delete()
            for position, src_data in enumerate(sources_data):
                resolved = self._resolve_fks(src_data)
                MatrixSource.objects.create(matrix=instance, position=position, **resolved)

        if columns_data is not None:
            instance.display_columns.all().delete()
            for position, col_data in enumerate(columns_data):
                MatrixDisplayColumn.objects.create(
                    matrix=instance,
                    position=position,
                    heading=col_data["heading"],
                    source_name=col_data["source"],
                )

        return instance

    def to_representation(self, instance):
        return MatrixSerializer(instance, context=self.context).to_representation(
            instance
        )
