"""Compact six-band DeepLabv3+ for the Banten CPU benchmark."""


def network(torch, classes):
    nn = torch.nn
    fn = nn.functional

    def conv(a, b, kernel=3, *, stride=1, rate=1, groups=1):
        padding = rate if kernel == 3 else 0
        return nn.Sequential(nn.Conv2d(a, b, kernel, stride, padding, dilation=rate, groups=groups, bias=False),
                             nn.GroupNorm(4, b), nn.ReLU())

    def separable(a, b, rate):
        return nn.Sequential(conv(a, a, rate=rate, groups=a), conv(a, b, 1))

    class DeepLabV3Plus(nn.Module):
        def __init__(self):
            super().__init__()
            self.low = conv(6, 16, stride=2)
            self.encoder = nn.Sequential(conv(16, 32, stride=2), separable(32, 32, 1))
            self.branches = nn.ModuleList([conv(32, 16, 1), *(separable(32, 16, rate) for rate in (1, 2, 4))])
            self.image_pool = nn.Sequential(nn.AdaptiveAvgPool2d(1), conv(32, 16, 1))
            self.context = conv(80, 24, 1)
            self.skip = conv(16, 8, 1)
            self.decoder = nn.Sequential(separable(32, 24, 1), separable(24, 16, 1), nn.Conv2d(16, classes, 1))

        def forward(self, image):
            low = self.low(image)
            high = self.encoder(low)
            pooled = fn.interpolate(self.image_pool(high), size=high.shape[-2:], mode="bilinear", align_corners=False)
            context = self.context(torch.cat([*(branch(high) for branch in self.branches), pooled], 1))
            context = fn.interpolate(context, size=low.shape[-2:], mode="bilinear", align_corners=False)
            output = self.decoder(torch.cat((context, self.skip(low)), 1))
            return fn.interpolate(output, size=image.shape[-2:], mode="bilinear", align_corners=False)

    return DeepLabV3Plus()
