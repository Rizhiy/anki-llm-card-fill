cwd="$(basename $(pwd))"

if [ "$cwd" != "anki-llm-card-fill" ]; then
	echo "Please run this script from project root"
	exit 1
fi

cd anki_llm_card_fill
zip -r ../llm_card_fill.ankiaddon config.json *.py model_settings/*
cd -
