"""
predictions/management/commands/train_weather_models.py

Django management command to execute reproducible ML weather model training.

Usage:
  python manage.py train_weather_models [--farm-id=<id>] [--targets=temperature,precipitation,...] [--n-estimators=100]
"""
import sys
from django.core.management.base import BaseCommand
from weather.models import Weather
from farms.models import Farm
from predictions.services.model_training import WeatherModelTrainer


class Command(BaseCommand):
    help = "Trains, evaluates, and persists machine learning weather prediction models."

    def add_arguments(self, parser):
        parser.add_argument(
            '--farm-id',
            type=int,
            default=None,
            help='Farm ID to train specific models for. If omitted, trains for the first farm with >= 50 historical records, or across all historical data.'
        )
        parser.add_argument(
            '--targets',
            type=str,
            default='temperature,precipitation,relative_humidity,wind_speed',
            help='Comma-separated target variables to train.'
        )
        parser.add_argument(
            '--n-estimators',
            type=int,
            default=100,
            help='Number of trees in Random Forest Regressor (default: 100).'
        )
        parser.add_argument(
            '--max-depth',
            type=int,
            default=12,
            help='Maximum tree depth (default: 12).'
        )
        parser.add_argument(
            '--global-model',
            action='store_true',
            default=False,
            help='Train a global model across all historical weather records rather than a specific farm.'
        )
        parser.add_argument(
            '--model-version',
            type=str,
            default='weather_v1',
            help='Model version prefix (default: weather_v1).'
        )

    def handle(self, *args, **options):
        is_global = options.get('global_model')
        farm_id = None if is_global else options.get('farm_id')
        targets_str = options.get('targets')
        n_estimators = options.get('n_estimators')
        max_depth = options.get('max_depth')
        version_prefix = options.get('model_version')

        targets = [t.strip() for t in targets_str.split(',') if t.strip()]

        # If not global and farm_id not explicitly given, discover farms with historical data
        if not is_global and not farm_id:
            farms_with_data = (
                Weather.objects.filter(forecast_type='HISTORICAL')
                .values_list('farm_id', flat=True)
                .distinct()
            )
            farms_list = list(farms_with_data)
            if farms_list:
                farm_id = farms_list[0]
                self.stdout.write(self.style.NOTICE(f"No --farm-id provided. Automatically selecting Farm {farm_id} with available historical records."))
            else:
                self.stdout.write(self.style.ERROR("No historical weather data found in the database. Please collect historical data in Stage 3 first."))
                return

        farm_obj = Farm.objects.filter(id=farm_id).first()
        farm_name = farm_obj.farm_name if farm_obj else f"Farm {farm_id}"

        self.stdout.write(self.style.MIGRATE_HEADING("============================================================"))
        self.stdout.write(self.style.MIGRATE_HEADING("CLIMAGPT — STAGE 5: AI WEATHER MODEL TRAINING PIPELINE"))
        self.stdout.write(self.style.MIGRATE_HEADING("============================================================"))
        self.stdout.write(f"Farm: {farm_name} (ID: {farm_id})")
        self.stdout.write(f"Algorithm: Random Forest Regressor (scikit-learn)")
        self.stdout.write(f"Baseline:  Persistence (Last-Value) Benchmark")
        self.stdout.write(f"Split:     Strict Chronological (Train 70% / Val 15% / Test 15% - No Leakage)")
        self.stdout.write(f"Targets:   {', '.join(targets)}")
        self.stdout.write("------------------------------------------------------------\n")

        trainer = WeatherModelTrainer(
            farm_id=farm_id,
            version_prefix=version_prefix,
        )

        try:
            report = trainer.train_all_targets(
                targets=targets,
                n_estimators=n_estimators,
                max_depth=max_depth,
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Training failed: {e}"))
            sys.exit(1)

        meta = report['dataset_metadata']
        self.stdout.write(self.style.SUCCESS("DATASET SUMMARY:"))
        self.stdout.write(f"  Total Validated Samples: {meta['total_samples']}")
        self.stdout.write(f"  Training Split (70%):     {meta['train_samples']} samples ({meta['train_start']} to {meta['train_end']})")
        self.stdout.write(f"  Validation Split (15%):   {meta['val_samples']} samples ({meta['val_start']} to {meta['val_end']})")
        self.stdout.write(f"  Testing Split (15%):      {meta['test_samples']} samples ({meta['test_start']} to {meta['test_end']})")
        self.stdout.write("============================================================\n")

        target_units = {
            'temperature': '°C',
            'precipitation': 'mm',
            'relative_humidity': '%',
            'wind_speed': 'km/h',
        }

        for target_name, res in report['targets'].items():
            unit = target_units.get(target_name, '')
            eval_info = res['evaluation']
            b = eval_info['baseline']
            m = eval_info['ml_model']
            pct = eval_info['mae_improvement_pct']

            self.stdout.write(self.style.MIGRATE_LABEL(f"Target: {target_name.upper()} ({unit})"))
            self.stdout.write(f"  Model Version: {res['version']}")
            self.stdout.write(f"  Artifact:      {res['artifact_path']}")
            self.stdout.write(f"  Test Samples:  {b['sample_count']}")
            self.stdout.write(f"  --------------------------------------------------")
            self.stdout.write(f"  {'Metric':<12} | {'Baseline (Persistence)':<22} | {'ML (Random Forest)':<20}")
            self.stdout.write(f"  --------------------------------------------------")
            self.stdout.write(f"  {'MAE':<12} | {b['mae']:<6} {unit:<15} | {m['mae']:<6} {unit:<13}")
            self.stdout.write(f"  {'RMSE':<12} | {b['rmse']:<6} {unit:<15} | {m['rmse']:<6} {unit:<13}")
            self.stdout.write(f"  {'R²':<12} | {b['r2']:<22} | {m['r2']:<20}")
            self.stdout.write(f"  {'MBE':<12} | {b['mbe']:<22} | {m['mbe']:<20}")
            self.stdout.write(f"  --------------------------------------------------")
            if pct > 0:
                self.stdout.write(self.style.SUCCESS(f"  ML Improvement: +{pct}% MAE reduction over Baseline"))
            else:
                self.stdout.write(self.style.WARNING(f"  ML Improvement: {pct}% relative to Baseline"))

            if res['top_features']:
                top_feats_str = ", ".join([f"{k} ({v})" for k, v in res['top_features']])
                self.stdout.write(f"  Top Features:   {top_feats_str}")
            self.stdout.write("\n")

        self.stdout.write(self.style.SUCCESS("All weather models trained and persisted successfully!"))
        self.stdout.write(self.style.MIGRATE_HEADING("============================================================"))
