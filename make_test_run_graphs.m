clear; clc; close all;

%% Dosya ayarları
xlsxFile = "test_artifacts/test_history.xlsx";
sheetName = "runs";

outputDir = "tez_test_grafikleri";
if ~exist(outputDir, "dir")
    mkdir(outputDir);
end

%% Excel oku
T = readtable(xlsxFile, "Sheet", sheetName, "VariableNamingRule", "preserve");

%% Kolonları al
runId = string(T.("run_id"));
timestamp = string(T.("timestamp"));

total = T.("total");
passed = T.("passed");
failed = T.("failed");
errors = T.("errors");
skipped = T.("skipped");
passRate = T.("pass_rate");

%% Run labels
n = height(T);
runLabels = strings(n,1);

for i = 1:n
    runLabels(i) = "Run " + string(i);
end

%% Effective pass rate hesapla
% Skipped testleri başarı oranı hesabından çıkarmak için:
effectiveTotal = passed + failed + errors;
effectivePassRate = zeros(n,1);

for i = 1:n
    if effectiveTotal(i) > 0
        effectivePassRate(i) = passed(i) / effectiveTotal(i) * 100;
    else
        effectivePassRate(i) = 0;
    end
end

%% Komut penceresi özeti
fprintf("\n--- TEST RUN HISTORY SUMMARY ---\n");
for i = 1:n
    fprintf("Run %d | Total: %d | Passed: %d | Failed: %d | Errors: %d | Skipped: %d | Raw Pass Rate: %.2f%% | Effective Pass Rate: %.2f%%\n", ...
        i, total(i), passed(i), failed(i), errors(i), skipped(i), passRate(i), effectivePassRate(i));
end

%% Grafik 1: Koşumlara göre raw pass rate
figure;
plot(1:n, passRate, "-o", "LineWidth", 1.8);
xticks(1:n);
xticklabels(runLabels);
ylabel("Pass Rate (%)");
ylim([0 100]);
title("Automated Test Runs: Pass Rate Improvement");
grid on;

for i = 1:n
    text(i, passRate(i), sprintf(" %.1f%%", passRate(i)), ...
        "VerticalAlignment", "bottom", "HorizontalAlignment", "center");
end

saveas(gcf, fullfile(outputDir, "01_test_pass_rate_improvement.png"));

%% Grafik 2: Effective pass rate
figure;
plot(1:n, effectivePassRate, "-o", "LineWidth", 1.8);
xticks(1:n);
xticklabels(runLabels);
ylabel("Effective Pass Rate (%)");
ylim([0 100]);
title("Automated Test Runs: Effective Pass Rate");
grid on;

for i = 1:n
    text(i, effectivePassRate(i), sprintf(" %.1f%%", effectivePassRate(i)), ...
        "VerticalAlignment", "bottom", "HorizontalAlignment", "center");
end

saveas(gcf, fullfile(outputDir, "02_effective_pass_rate.png"));

%% Grafik 3: Pass / fail / error / skipped sayıları
figure;
bar(categorical(runLabels), [passed failed errors skipped], "stacked");
ylabel("Test Count");
title("Automated Test Runs: Result Distribution");
legend("Passed", "Failed", "Errors", "Skipped", "Location", "best");
grid on;

saveas(gcf, fullfile(outputDir, "03_test_result_distribution.png"));

%% Grafik 4: Final test sonucu dağılımı
finalPassed = passed(end);
finalFailed = failed(end);
finalErrors = errors(end);
finalSkipped = skipped(end);

figure;
bar(categorical(["Passed", "Failed", "Errors", "Skipped"]), ...
    [finalPassed, finalFailed, finalErrors, finalSkipped]);
ylabel("Test Count");
title("Final Automated Test Result");
grid on;

values = [finalPassed, finalFailed, finalErrors, finalSkipped];
for i = 1:numel(values)
    text(i, values(i), sprintf(" %d", values(i)), ...
        "VerticalAlignment", "bottom", "HorizontalAlignment", "center");
end

saveas(gcf, fullfile(outputDir, "04_final_test_result.png"));

%% Grafik 5: Fail + error azalımı
figure;
plot(1:n, failed + errors, "-o", "LineWidth", 1.8);
xticks(1:n);
xticklabels(runLabels);
ylabel("Failed + Error Count");
title("Automated Test Runs: Failure/Error Reduction");
grid on;

for i = 1:n
    text(i, failed(i) + errors(i), sprintf(" %d", failed(i) + errors(i)), ...
        "VerticalAlignment", "bottom", "HorizontalAlignment", "center");
end

saveas(gcf, fullfile(outputDir, "05_failure_error_reduction.png"));

%% Özet tabloyu dışarı kaydet
summaryOut = table( ...
    runLabels, timestamp, total, passed, failed, errors, skipped, passRate, effectivePassRate, ...
    'VariableNames', {'Run', 'Timestamp', 'Total', 'Passed', 'Failed', 'Errors', 'Skipped', 'RawPassRate', 'EffectivePassRate'} ...
);

writetable(summaryOut, fullfile(outputDir, "test_run_summary_for_presentation.xlsx"));

fprintf("\nGrafikler '%s' klasorune kaydedildi.\n", outputDir);