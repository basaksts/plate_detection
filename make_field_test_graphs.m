clear; clc; close all;

%% Dosya ayarları
xlsxFile = "canli_test_degerlendirme_sablonu.xlsx";
sheetName = "01_Degerlendirme";

outputDir = "tez_grafikleri";
if ~exist(outputDir, "dir")
    mkdir(outputDir);
end

%% Excel oku
T = readtable(xlsxFile, "Sheet", sheetName, "VariableNamingRule", "preserve");

%% Gerekli sütunları al
systemPlate = string(T.("sistem_plaka_dosyadan"));
truePlate   = string(T.("gercek_plaka_MANUEL"));
plateVisible = string(T.("plaka_gorunuyor_mu"));
systemDetected = string(T.("sistem_yakaladi_mi"));
exactCorrect = string(T.("tam_dogru_mu"));

%% Temizleme
systemPlate = upper(strtrim(systemPlate));
truePlate   = upper(strtrim(truePlate));
plateVisible = strtrim(plateVisible);
systemDetected = strtrim(systemDetected);
exactCorrect = strtrim(exactCorrect);

validRows = truePlate ~= "" & plateVisible == "Evet" & systemDetected == "Evet";

systemPlateValid = systemPlate(validRows);
truePlateValid = truePlate(validRows);
exactCorrectValid = exactCorrect(validRows);

%% Temel sayımlar
totalCount = numel(truePlateValid);
correctCount = sum(exactCorrectValid == "Evet");
wrongCount = sum(exactCorrectValid == "Hayır");

exactAccuracy = correctCount / totalCount * 100;
errorRate = wrongCount / totalCount * 100;

%% Karakter bazlı doğruluk hesapla
totalChars = 0;
correctChars = 0;

errorType = strings(totalCount, 1);

for i = 1:totalCount
    s = erase(systemPlateValid(i), " ");
    g = erase(truePlateValid(i), " ");

    dist = levenshteinDistance(char(s), char(g));
    maxLen = max(strlength(s), strlength(g));

    correctChars = correctChars + double(maxLen - dist);
    totalChars = totalChars + double(maxLen);

    lenDiff = strlength(s) - strlength(g);

    if s == g
        errorType(i) = "Tam doğru";
    elseif lenDiff == 0
        errorType(i) = "Aynı uzunlukta karakter hatası";
    elseif lenDiff == -1
        errorType(i) = "1 karakter eksik";
    elseif lenDiff == -2
        errorType(i) = "2 karakter eksik";
    elseif lenDiff == 1
        errorType(i) = "1 karakter fazla";
    else
        errorType(i) = "Diğer uzunluk farkı";
    end
end

charAccuracy = correctChars / totalChars * 100;

%% Komut ekranı özeti
fprintf("\n--- SAHA TESTI OZETI ---\n");
fprintf("Toplam degerlendirilen kayit: %d\n", totalCount);
fprintf("Tam dogru okunan plaka: %d\n", correctCount);
fprintf("Yanlis okunan plaka: %d\n", wrongCount);
fprintf("Tam plaka dogrulugu: %.2f%%\n", exactAccuracy);
fprintf("Hata orani: %.2f%%\n", errorRate);
fprintf("Karakter bazli dogruluk: %.2f%%\n", charAccuracy);

%% Grafik 1: Doğru / yanlış dağılımı
figure;
bar(categorical(["Tam doğru", "Yanlış"]), [correctCount, wrongCount]);
ylabel("Kayıt Sayısı");
title("Saha Testi: Tam Doğru ve Yanlış Plaka Okuma Dağılımı");
grid on;

text(1, correctCount, sprintf(" %d", correctCount), "VerticalAlignment", "bottom");
text(2, wrongCount, sprintf(" %d", wrongCount), "VerticalAlignment", "bottom");

saveas(gcf, fullfile(outputDir, "01_dogru_yanlis_dagilimi.png"));

%% Grafik 2: Tam plaka doğruluğu vs karakter doğruluğu
figure;
bar(categorical(["Tam Plaka Doğruluğu", "Karakter Bazlı Doğruluk"]), ...
    [exactAccuracy, charAccuracy]);
ylabel("Doğruluk (%)");
ylim([0 100]);
title("Saha Testi: Tam Plaka ve Karakter Bazlı Doğruluk");
grid on;

text(1, exactAccuracy, sprintf(" %.2f%%", exactAccuracy), "VerticalAlignment", "bottom");
text(2, charAccuracy, sprintf(" %.2f%%", charAccuracy), "VerticalAlignment", "bottom");

saveas(gcf, fullfile(outputDir, "02_dogruluk_karsilastirma.png"));

%% Grafik 3: Hata tipi dağılımı
wrongErrorType = errorType(errorType ~= "Tam doğru");

categories = unique(wrongErrorType, "stable");
counts = zeros(numel(categories), 1);

for i = 1:numel(categories)
    counts(i) = sum(wrongErrorType == categories(i));
end

figure;
bar(categorical(categories), counts);
ylabel("Hata Sayısı");
title("Saha Testi: Hata Tipi Dağılımı");
grid on;
xtickangle(25);

for i = 1:numel(counts)
    text(i, counts(i), sprintf(" %d", counts(i)), "VerticalAlignment", "bottom");
end

saveas(gcf, fullfile(outputDir, "03_hata_tipi_dagilimi.png"));

%% Grafik 4: Sunum için yüzde bazlı doğru/yanlış grafiği
figure;

percentValues = [exactAccuracy, errorRate];

bar(categorical({'Tam Doğru', 'Yanlış'}), percentValues);
ylabel('Oran (%)');
ylim([0 100]);
title('Saha Testi: Plaka Okuma Başarı Oranı');
grid on;

text(1, exactAccuracy, sprintf(' %.2f%%', exactAccuracy), ...
    'VerticalAlignment', 'bottom', 'HorizontalAlignment', 'center');

text(2, errorRate, sprintf(' %.2f%%', errorRate), ...
    'VerticalAlignment', 'bottom', 'HorizontalAlignment', 'center');

saveas(gcf, fullfile(outputDir, '04_yuzde_dogru_yanlis.png'));

%% Sonuçları tablo olarak kaydet
summaryTable = table( ...
    totalCount, correctCount, wrongCount, exactAccuracy, errorRate, charAccuracy, ...
    'VariableNames', {'Toplam', 'TamDogru', 'Yanlis', 'TamPlakaDogrulugu', 'HataOrani', 'KarakterDogrulugu'} ...
);

writetable(summaryTable, fullfile(outputDir, "saha_testi_ozet_sonuclar.xlsx"));

fprintf("\nGrafikler '%s' klasorune kaydedildi.\n", outputDir);

%% Lokal fonksiyon: Levenshtein distance
function d = levenshteinDistance(a, b)
    m = length(a);
    n = length(b);

    D = zeros(m+1, n+1);

    for i = 1:m+1
        D(i,1) = i-1;
    end

    for j = 1:n+1
        D(1,j) = j-1;
    end

    for i = 2:m+1
        for j = 2:n+1
            cost = ~(a(i-1) == b(j-1));
            D(i,j) = min([ ...
                D(i-1,j) + 1, ...
                D(i,j-1) + 1, ...
                D(i-1,j-1) + cost ...
            ]);
        end
    end

    d = D(m+1,n+1);
end